# modules/yolo_runtime.py
from __future__ import annotations

import cv2
import time
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from ultralytics import YOLO
from modules.notifications.audio_alert import init_audio, play_alert_async
from modules.storage.cloudflare_r2 import R2Config, CloudflareR2
from modules.video.video_recorder import RecorderConfig, VideoRecorder
from modules.video.recording_worker import RecordingConfig, RecordingWorker
from modules.notifications.line_notify import LineConfig, push_message
from modules.core.event_worker import WorkerConfig, EventWorker
from modules.video.rtsp_reader import RTSPReader
from modules.settings import Settings
from modules.core.shop_state_manager import ShopStateManager
from modules.core.shop_config import get_shop_config
from modules.video.video_source import get_reader
from utils.r2_keys import make_datetime_key
from utils import (
    ENTRY_ROI_PTS,
    INSIDE_ROI_PTS,
    YOLO_CONF,
    YOLO_IOU,
    YOLO_MAX_DET,
    YOLO_CLASSES,
    EMPTY_THRESHOLD,
    SPATIAL_ENTRY_COOLDOWN,
    SPATIAL_ENTRY_RADIUS,
    TRACK_HISTORY_MAX_LEN,
    RECORDER_FPS,
    RECORDER_SEGMENT_MINUTES,
    EVENT_WORKER_MAX_QUEUE,
)
import logging

logger = logging.getLogger(__name__)


class SpatialEntryCounter:
    """
    位置去重計數器：同一位置在冷卻時間內只計算一次進店。
    用於解決 Track ID 不穩定導致的重複計數問題。
    """

    def __init__(self, cooldown_seconds: float = 5.0, radius: float = 100.0):
        self.cooldown = cooldown_seconds
        self.radius = radius
        # [(x, y, timestamp), ...]
        self.recent_entries: list[tuple[float, float, float]] = []

    def try_count(self, x: float, y: float) -> bool:
        """
        嘗試計數：如果該位置附近最近沒計過，回傳 True 並記錄。
        """
        now = time.time()

        # 清理過期記錄
        self.recent_entries = [
            (ex, ey, et) for ex, ey, et in self.recent_entries
            if now - et < self.cooldown
        ]

        # 檢查附近是否有最近的計數
        for ex, ey, et in self.recent_entries:
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < self.radius:
                return False  # 太近，不計

        # 記錄並計數
        self.recent_entries.append((x, y, now))
        return True


@dataclass
class YoloRuntime:
    """
    負責整個 YOLO + RTSP + 錄影 + 通知 的「長期運作」流程。
    原本 main() 裡的內容，大部分都搬進來。
    """
    settings: Settings
    show_window: bool = False       # 是否顯示 OpenCV 視窗
    run_in_thread: bool = True      # True: 跑在背景 thread（給 server 用）
    # shop_state_manager: ShopStateManager = field(
    #     default_factory=lambda: ShopStateManager
    # )
    shop_state_manager: ShopStateManager = field(
        default_factory=ShopStateManager
    )
    _thread: Optional[threading.Thread] = field(init=False, default=None)
    _stop: threading.Event = field(init=False, default_factory=threading.Event)

    # 下面這些屬性會在 _init_components() 裡被設定
    rec: Optional[VideoRecorder] = None
    recording_worker: Optional[RecordingWorker] = None
    reader: Optional[RTSPReader] = field(init=False, default=None)
    worker: Optional[EventWorker] = None
    r2: Optional[CloudflareR2] = None
    line_cfg: Optional[LineConfig] = None
    model: Optional[YOLO] = None

    # 這些是 tracking 用的狀態（之後你也可以拿來做狀態查詢 API）
    track_history: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)
    last_zone: Dict[int, str] = field(default_factory=dict)

    # 位置去重計數器（解決 ID 不穩定問題）
    entry_counter: SpatialEntryCounter = field(
        default_factory=lambda: SpatialEntryCounter(
            cooldown_seconds=SPATIAL_ENTRY_COOLDOWN,
            radius=SPATIAL_ENTRY_RADIUS,
        )
    )

    notify_cooldown: float = 10.0

    # Track 清理設定
    _last_cleanup_time: float = field(init=False, default=0.0)
    _cleanup_interval: float = 60.0  # 每 60 秒清理一次

    def start(self) -> None:
        """由外部呼叫，啟動整個 YOLO runtime。"""
        self._stop.clear()
        self._init_components()

        if self.run_in_thread:
            # 給 server 用：背景 thread 執行
            self._thread = threading.Thread(
                target=self._loop,
                name="YoloRuntimeLoop",
                daemon=True,
            )
            self._thread.start()
        else:
            # 給 debug 用：直接在主執行緒跑（允許 cv2.namedWindow）
            self._loop()

    def stop(self) -> None:
        """由外部（例如 FastAPI shutdown）呼叫，優雅關閉。"""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        # 清理資源
        for fn in [
            # getattr(self.reader, "stop", None),  # 關掉 不然 WebRTC就壞了
            getattr(self.recording_worker, "stop", None),
            getattr(self.rec, "stop", None),
            cv2.destroyAllWindows if self.show_window else None,
        ]:
            if callable(fn):
                try:
                    fn()
                except Exception as e:
                    logger.exception("Cleanup error")

        # debug 輸出
        logger.debug("Track history: %s", self.track_history)
        logger.debug("Last zone: %s", self.last_zone)

    # === 初始化部分 ===

    def _init_components(self) -> None:
        """初始化所有相依元件，統一從 self.settings 拿設定。"""
        cfg = self.settings

        # --- LINE 設定 ---
        self.line_cfg = LineConfig(
            access_token=cfg.line_access_token,
            user_file=str(cfg.user_id_file_path) if cfg.user_id_file_path else None,
        )

        # --- 背景事件 worker（送通知用）---
        self.worker = EventWorker(WorkerConfig(
            max_queue=EVENT_WORKER_MAX_QUEUE,
            drop_if_full=True,
        ))

        # --- Cloudflare R2 ---
        self.r2 = CloudflareR2(R2Config(
            access_key=cfg.r2_access_key,
            secret_key=cfg.r2_secret_key,
            bucket=cfg.r2_bucket,
            endpoint=cfg.r2_endpoint,
            public_url=cfg.r2_public_url,
        ))

        # --- 音效 ---
        if cfg.audio_alert_path:
            init_audio(str(cfg.audio_alert_path))

        # --- 錄影模組 ---
        self.rec = VideoRecorder(RecorderConfig(
            camera_id="cam1",  # 輸出到 recordings/cam1/{date}/
            save_raw=True,
            save_annot=False,
            fps=RECORDER_FPS,
            segment_minutes=RECORDER_SEGMENT_MINUTES,
        ))
        self.rec.start()

        self.recording_worker = RecordingWorker(self.rec, RecordingConfig(fps=RECORDER_FPS))
        self.recording_worker.start()

        # --- RTSP 讀取 ---
        self.reader = get_reader()

        # --- YOLO 模型 ---
        if not cfg.yolo26_model_m_path:
            raise RuntimeError("YOLO26_MODEL_M_PATH 未設定")

        self.model = YOLO(str(cfg.yolo26_model_m_path))

        # --- 通知冷卻時間（從 shop.json 讀取）---
        shop_cfg = get_shop_config()
        self.notify_cooldown = shop_cfg.entry_cooldown

    # === 主迴圈 ===

    def _loop(self) -> None:
        """
        原本 main() 裡的 while True，大致搬過來。
        注意：這裡不要再呼叫 load_dotenv()，也不要再做初始化。
        """
        cfg = self.settings

        window_name = "YOLO11n - Camera"
        if self.show_window:
            # 使用 WINDOW_NORMAL 允許視窗縮放，避免高解析度畫面超出螢幕被裁切
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window_name, self._on_click)

        prev_time = 0.0
        last_notify_ts = 0.0
        last_after_hours_notify_ts = 0.0  # 非營業時段通知冷卻
        track_history = self.track_history
        last_zone = self.last_zone
        prev_inside_count = 0  # 上一幀店內人數（用於通知判斷）

        # 連續幀驗證：避免偵測閃爍導致誤判
        empty_frame_count = 0

        while not self._stop.is_set():
            # 讀取最新 frame
            if not self.reader:
                break

            frame, ts = self.reader.get_latest()
            if frame is None:
                cv2.waitKey(1)
                continue

            height, width = frame.shape[:2]
            # 鏡像翻轉
            # frame = cv2.flip(frame, 1)

            current_time = time.time()
            fps = 1 / (current_time - prev_time) if prev_time != 0 else 0
            prev_time = current_time

            # YOLO track
            assert self.model is not None
            tracker_cfg = (
                str(cfg.tracker_bytetrack_path)
                if cfg.tracker_bytetrack_path
                else None
            )

            results = self.model.track(
                frame,
                tracker=tracker_cfg,
                persist=True,
                conf=YOLO_CONF,
                iou=YOLO_IOU,
                max_det=YOLO_MAX_DET,
                classes=YOLO_CLASSES,
                verbose=False
            )
            r = results[0]
            annotated_frame = r.plot()

            # !!~ 繪製 ROI用
            # cv2.imwrite("draw_roi.jpg", annotated_frame)

            # 錄影
            if self.recording_worker:
                self.recording_worker.update(raw_frame=frame)

            if r.boxes.id is not None:
                ids = r.boxes.id.int().cpu().tolist()
                boxes = r.boxes.xywh.cpu().tolist()

                # 統計這一幀店內/門口的偵測數量
                inside_count_this_frame = 0
                door_count_this_frame = 0
                # 收集 door→inside 轉換的位置（用於客流量計數）
                door_to_inside_positions: list[tuple[int, int]] = []

                # 處理每個物件
                for obj_id, (cx, cy, w, h) in zip(ids, boxes):
                    cx = int(cx)
                    cy = int(cy)

                    in_door = cv2.pointPolygonTest(ENTRY_ROI_PTS, (cx, cy), False) >= 0
                    in_inside = cv2.pointPolygonTest(
                        INSIDE_ROI_PTS, (cx, cy), False) >= 0

                    if in_inside:
                        zone_now = "inside"
                        inside_count_this_frame += 1
                    elif in_door:
                        zone_now = "door"
                        door_count_this_frame += 1
                    else:
                        zone_now = "none"

                    zone_prev = last_zone.get(obj_id, "none")

                    # 偵測 door → inside 轉換（用於客流量 + 通知）
                    if zone_prev == "door" and zone_now == "inside":
                        door_to_inside_positions.append((cx, cy))

                        # 通知條件：上一幀店內沒人 + 有人從門口進店
                        if (
                            current_time - last_notify_ts > self.notify_cooldown
                            and prev_inside_count == 0
                        ):
                            last_notify_ts = current_time
                            snap = annotated_frame.copy()
                            self._submit_notify_job(snap)

                            cv2.putText(
                                img=annotated_frame,
                                text="Notify",
                                org=(1650, 30),
                                fontFace=cv2.FONT_HERSHEY_DUPLEX,
                                fontScale=1,
                                color=(35, 0, 255),
                                thickness=2,
                            )

                    last_zone[obj_id] = zone_now

                    # 軌跡
                    if obj_id not in track_history:
                        track_history[obj_id] = []
                    track_history[obj_id].append((cx, cy))
                    if len(track_history[obj_id]) > TRACK_HISTORY_MAX_LEN:
                        track_history[obj_id] = track_history[obj_id][-TRACK_HISTORY_MAX_LEN:]

                    if len(track_history[obj_id]) >= 2:
                        for i in range(1, len(track_history[obj_id])):
                            cv2.line(
                                img=annotated_frame,
                                pt1=track_history[obj_id][i - 1],
                                pt2=track_history[obj_id][i],
                                color=(0, 255, 0),
                                thickness=2,
                            )

                    # 繪製定位點
                    cv2.circle(
                        img=annotated_frame,
                        center=(cx, cy),
                        radius=5,
                        color=(252, 0, 168),
                        thickness=2,
                    )

                # === 更新狀態 ===
                # 1. 即時人數：直接用偵測數量（不依賴 ID 穩定性）
                self.shop_state_manager.set_inside_count(inside_count_this_frame)

                # 連續幀驗證：避免偵測閃爍
                if inside_count_this_frame > 0:
                    empty_frame_count = 0
                    prev_inside_count = inside_count_this_frame
                else:
                    empty_frame_count += 1
                    # 只有連續多幀沒人才更新 prev_inside_count = 0
                    if empty_frame_count >= EMPTY_THRESHOLD:
                        prev_inside_count = 0

                # 2. 客流量：door→inside + 位置去重（避免 ID 跳動重複計數）
                for x, y in door_to_inside_positions:
                    if self.entry_counter.try_count(x, y):
                        self.shop_state_manager.record_entry()
                        logger.debug("Entry counted at (%d, %d)", x, y)

                # 3. 非營業時段逗留通知
                total_detected = inside_count_this_frame + door_count_this_frame
                shop_cfg = get_shop_config()
                if (
                    shop_cfg.is_after_hours()
                    and total_detected > 0
                    and current_time - last_after_hours_notify_ts > shop_cfg.after_hours_cooldown
                ):
                    last_after_hours_notify_ts = current_time
                    self._submit_notify_job(
                        annotated_frame,
                        msg=f"⚠️ 非營業時段偵測到 {total_detected} 人"
                    )
                    logger.info("After-hours alert: detected %d person(s)",
                                total_detected)

                # 4. 定期清理過期的追蹤記錄
                self._cleanup_stale_tracks(set(ids))

            else:
                # 這一幀完全沒偵測到人
                self.shop_state_manager.set_inside_count(0)

                # 連續幀驗證：避免偵測閃爍
                empty_frame_count += 1
                if empty_frame_count >= EMPTY_THRESHOLD:
                    prev_inside_count = 0

            # FPS 顯示
            cv2.putText(
                img=annotated_frame,
                text=f"FPS: {int(fps)}",
                org=(10, 30),
                fontFace=cv2.FONT_HERSHEY_DUPLEX,
                fontScale=1,
                color=(35, 255, 150),
                thickness=2,
            )

            # ROI
            cv2.polylines(
                img=annotated_frame,
                pts=[ENTRY_ROI_PTS],
                isClosed=True,
                color=(0, 0, 255),
                thickness=5,
            )
            cv2.polylines(
                img=annotated_frame,
                pts=[INSIDE_ROI_PTS],
                isClosed=True,
                color=(0, 255, 0),
                thickness=5,
            )

            if self.show_window:
                cv2.imshow(window_name, annotated_frame)
                cv2.resizeWindow(window_name, width, height)
                # 按 q 離開
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self._stop.set()
            else:
                # headless 模式避免一直空轉
                time.sleep(0.01)

        # loop 結束 → 等 stop() 做正式清理

    # === 小工具 ===
    def _cleanup_stale_tracks(self, active_ids: set) -> None:
        """
        清理已離開畫面的追蹤記錄，避免記憶體無限增長。
        只保留當前活躍的 track_id。
        """
        current_time = time.time()

        # 檢查是否需要清理（每 _cleanup_interval 秒一次）
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return

        self._last_cleanup_time = current_time

        # 找出過期的 ID
        stale_history_ids = set(self.track_history.keys()) - active_ids
        stale_zone_ids = set(self.last_zone.keys()) - active_ids

        # 清理
        cleaned_count = 0
        for stale_id in stale_history_ids:
            self.track_history.pop(stale_id, None)
            cleaned_count += 1
        for stale_id in stale_zone_ids:
            self.last_zone.pop(stale_id, None)

        if cleaned_count > 0:
            logger.debug(
                "Cleaned %d stale tracks. Active: %d, History size: %d, Zone size: %d",
                cleaned_count, len(active_ids),
                len(self.track_history), len(self.last_zone)
            )

    def _on_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            logger.debug("Mouse click coordinate: (%d, %d)", x, y)

    def _submit_notify_job(self, frame, msg: str = "有人進店囉"):
        if not (self.worker and self.line_cfg and self.r2):
            return

        cfg = self.settings
        audio_path = str(cfg.audio_alert_path) if cfg.audio_alert_path else None

        snap = frame.copy()
        line_cfg = self.line_cfg
        r2 = self.r2

        def notify_job():
            # 1) 語音提醒
            if audio_path:
                play_alert_async(times=1, audio_path=audio_path)

            # 2) resize + encode
            resize_frame = cv2.resize(snap, (960, 540))
            ok, buf = cv2.imencode(".jpg", resize_frame)
            if not ok:
                logger.error("OpenCV cv2.imencode failed")
                return

            # 3) Cloudflare R2 上傳
            key = make_datetime_key(ext=".jpg", prefix="cctv")
            try:
                url = r2.upload_bytes(
                    buf.tobytes(),
                    key=key,
                    content_type="image/jpeg",
                )
            except Exception as e:
                logger.exception("Cloudflare upload bytes failed")
                url = None

            # 4) LINE push
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                push_message(
                    cfg=line_cfg,
                    msg=f"{now_str}\n{msg}",
                    img_url=url,
                )
            except Exception as e:
                logger.exception("LINE push message failed")

        accepted = self.worker.submit(notify_job)
        if not accepted:
            logger.debug("Notify job dropped (queue full)")

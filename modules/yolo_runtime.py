# modules/yolo_runtime.py
from __future__ import annotations

import cv2
import time
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from ultralytics import YOLO
from modules.audio_alert import init_audio, play_alert_async
from modules.cloudflare_r2 import R2Config, CloudflareR2
from modules.video_recorder import RecorderConfig, VideoRecorder
from modules.recording_worker import RecordingConfig, RecordingWorker
from modules.line_notify import LineConfig, push_message
from modules.event_worker import WorkerConfig, EventWorker
from modules.rtsp_reader import RTSPReader
from modules.settings import Settings
from modules.shop_state_manager import ShopStateManager
from modules.video_source import get_reader
from utils.r2_keys import make_datetime_key
from utils import (
    ENTRY_ROI_PTS,
    INSIDE_ROI_PTS,
    MAX_DISAPPEAR
)
import logging

logger = logging.getLogger(__name__)


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
    disappear_counter: Dict[int, int] = field(default_factory=dict)
    last_zone: Dict[int, str] = field(default_factory=dict)

    notify_cooldown: float = 10.0

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
        logger.debug("Track history self.track_history: %s", self.track_history)
        logger.debug("Disappear counte self.disappear_counter: %s",
                     self.disappear_counter)
        logger.debug("Target last zone self.last_zone: %s", self.last_zone)

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
            max_queue=10,
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
            save_raw=True,
            save_annot=False,
            fps=30,
        ))
        self.rec.start()

        self.recording_worker = RecordingWorker(self.rec, RecordingConfig(fps=30))
        self.recording_worker.start()

        # --- RTSP 讀取 ---
        self.reader = get_reader()

        # --- YOLO 模型 ---
        if not cfg.yolo11_model_m_path:
            raise RuntimeError("YOLO11_MODEL_M_PATH 未設定")
        self.model = YOLO(str(cfg.yolo11_model_m_path))

        # --- 通知冷卻時間 ---
        # settings.notify_cooldown 是 float / Optional[float]
        self.notify_cooldown = float(cfg.notify_cooldown or 10.0)

    # === 主迴圈 ===

    def _loop(self) -> None:
        """
        原本 main() 裡的 while True，大致搬過來。
        注意：這裡不要再呼叫 load_dotenv()，也不要再做初始化。
        """
        cfg = self.settings

        window_name = "YOLO11n - Camera"
        if self.show_window:
            cv2.namedWindow(window_name)
            cv2.setMouseCallback(window_name, self._on_click)

        prev_time = 0.0
        last_notify_ts = 0.0
        track_history = self.track_history
        disappear_counter = self.disappear_counter
        last_zone = self.last_zone

        while not self._stop.is_set():
            # 讀取最新 frame
            if not self.reader:
                break

            frame, ts = self.reader.get_latest()
            if frame is None:
                cv2.waitKey(1)
                continue

            frame = cv2.flip(frame, 1)

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
                conf=0.5,
                iou=0.6,
                classes=[47, 49],  # TODO: 之後改回 person
                verbose=False
            )
            r = results[0]
            annotated_frame = r.plot()

            # 錄影
            if self.recording_worker:
                self.recording_worker.update(raw_frame=frame)

            if r.boxes.id is not None:
                ids = r.boxes.id.int().cpu().tolist()
                boxes = r.boxes.xywh.cpu().tolist()
                current_ids = set(ids)

                # 清理消失的 id，計算離開幾幀
                for old_id in list(track_history.keys()):
                    if old_id not in current_ids:
                        disappear_counter[old_id] = disappear_counter.get(old_id, 0) + 1
                    else:
                        disappear_counter[old_id] = 0

                # 計算上一幀在綠區的人數
                prev_inside_ids = {i for i, z in last_zone.items() if z == "inside"}
                inside_now_ids: set[int] = set()

                # 處理每個物件
                for obj_id, (cx, cy, w, h) in zip(ids, boxes):
                    cx, cy = int(cx), int(cy)

                    in_door = cv2.pointPolygonTest(ENTRY_ROI_PTS, (cx, cy), False) >= 0
                    in_inside = cv2.pointPolygonTest(
                        INSIDE_ROI_PTS, (cx, cy), False) >= 0

                    if in_inside:
                        zone_now = "inside"
                        inside_now_ids.add(obj_id)
                    elif in_door:
                        zone_now = "door"
                    else:
                        zone_now = "none"

                    zone_prev = last_zone.get(obj_id, "none")

                    # 通知條件：上一幀綠區沒人 + 這個人從 door 進 inside
                    if (
                        current_time - last_notify_ts > self.notify_cooldown
                        and len(prev_inside_ids) == 0
                        and zone_prev == "door"
                        and zone_now == "inside"
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
                    if len(track_history[obj_id]) > 20:
                        track_history[obj_id] = track_history[obj_id][-20:]

                    if len(track_history[obj_id]) >= 2:
                        for i in range(1, len(track_history[obj_id])):
                            cv2.line(
                                img=annotated_frame,
                                pt1=track_history[obj_id][i - 1],
                                pt2=track_history[obj_id][i],
                                color=(0, 255, 0),
                                thickness=2,
                            )

                    cv2.circle(
                        img=annotated_frame,
                        center=(cx, cy),
                        radius=5,
                        color=(252, 0, 168),
                        thickness=2,
                    )

                # 計算 new_entries / leaves（正常有偵測的情況） ---
                new_entries = inside_now_ids - prev_inside_ids
                leaves = prev_inside_ids - inside_now_ids

                # !!! 如果某個 inside ID 的 disappear_counter 太大，也當成 leaves
                for pid in list(prev_inside_ids):
                    if disappear_counter.get(pid, 0) > MAX_DISAPPEAR:
                        leaves.add(pid)
                        # 從狀態裡移除
                        track_history.pop(pid, None)
                        disappear_counter.pop(pid, None)
                        last_zone.pop(pid, None)

                if new_entries or leaves:
                    self._update_shop_state(new_entries=new_entries, leaves=leaves)
            else:
                # ✅ 這一幀完全沒偵測到人 (r.boxes.id is None)
                prev_inside_ids = {i for i, z in last_zone.items() if z == "inside"}
                leaves: set[int] = set()

                # 把所有既有 ID 的 disappear_counter +1
                for old_id in list(track_history.keys()):
                    disappear_counter[old_id] = disappear_counter.get(old_id, 0) + 1

                for pid in list(prev_inside_ids):
                    if disappear_counter.get(pid, 0) > MAX_DISAPPEAR:
                        leaves.add(pid)
                        track_history.pop(pid, None)
                        disappear_counter.pop(pid, None)
                        last_zone.pop(pid, None)

                if leaves:
                    logger.debug(
                        "No detections, leaves after disappea > %d: %s", MAX_DISAPPEAR, leaves)
                    self._update_shop_state(new_entries=set(), leaves=leaves)

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
                # 按 q 離開
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self._stop.set()
            else:
                # headless 模式避免一直空轉
                time.sleep(0.01)

        # loop 結束 → 等 stop() 做正式清理

    # === 小工具 ===
    def _on_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            logger.debug("Mouse click coordinate: (%d, %d)", x, y)

    def _update_shop_state(self, new_entries: set[int], leaves: set[int]):
        for _id in new_entries:
            self.shop_state_manager.record_entry()
        for _id in leaves:
            self.shop_state_manager.exit_one()

    def _submit_notify_job(self, frame):
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
                    msg=f"{now_str}\n有人進店囉",
                    img_url=url,
                )
            except Exception as e:
                logger.exception("LINE push message failed")

        accepted = self.worker.submit(notify_job)
        if not accepted:
            logger.debug("Notify job dropped (queue full)")
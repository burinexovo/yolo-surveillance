import os
import cv2
import time
from dotenv import load_dotenv
from datetime import datetime
from ultralytics import YOLO
from modules.audio_alert import init_audio, play_alert_async
from modules.cloudflare_r2 import R2Config, CloudflareR2
from modules.video_recorder import RecorderConfig, VideoRecorder
from modules.recording_worker import RecordingConfig, RecordingWorker
from modules.line_notify import LineConfig, push_message
from modules.event_worker import WorkerConfig, EventWorker
from modules.rtsp_reader import RTSPReaderConfig, RTSPReader
from utils.r2_keys import make_datetime_key
from utils import (
    ENTRY_ROI_PTS,
    INSIDE_ROI_PTS,
)


# === 0. 滑鼠事件 callback 函式 ===
def on_click(event, x, y, flags, param):
    # 左鍵按下去的時候觸發
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"🖱️ 滑鼠左鍵點擊座標：({x}, {y})")


def main():
    load_dotenv()

    # Doing = True  # @TEST
    rec = VideoRecorder(RecorderConfig(save_raw=True, save_annot=False, fps=30))
    rec.start()

    recording_cfg = RecordingConfig(fps=30)
    recording_worker = RecordingWorker(rec, recording_cfg)
    recording_worker.start()

    AUDIO_ALERT_PATH = os.getenv("AUDIO_ALERT_PATH")
    TRACKER_BYTETRACK_PATH = os.getenv("TRACKER_BYTETRACK_PATH")
    RTSP_URL_STREAM1 = os.getenv("RTSP_URL_STREAM1")
    RTSP_URL_STREAM2 = os.getenv("RTSP_URL_STREAM2")
    DEVICE_CAMERA0 = os.getenv("DEVICE_CAMERA0")

    line_cfg = LineConfig(
        access_token=os.getenv("LINE_ACCESS_TOKEN"),
        user_file=os.getenv("USER_ID_FILE_PATH"),
    )

    worker = EventWorker(WorkerConfig(
        max_queue=10,
        drop_if_full=True,
    ))

    r2 = CloudflareR2(R2Config(
        access_key=os.getenv("R2_ACCESS_KEY"),
        secret_key=os.getenv("R2_SECRET_KEY"),
        bucket=os.getenv("R2_BUCKET"),
        endpoint=os.getenv("R2_ENDPOINT"),
        public_url=os.getenv("R2_PUBLIC_URL"),
    ))

    # 初始化音訊
    init_audio(AUDIO_ALERT_PATH)

    # 載入 YOLO11n 模型
    model = YOLO(os.getenv("YOLO11_MODEL_M_PATH"))

    # 開啟攝影機（0 = macbook 內建鏡頭）
    # cap = cv2.VideoCapture(0)
    # cap = cv2.VideoCapture(RTSP_URL_STREAM1, cv2.CAP_FFMPEG)
    # cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 盡量只保留 1 張在buffer
    # cap.set(cv2.CAP_PROP_FPS, 30)
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # 攝像頭開不了
    # if not cap.isOpened():
    #     print("❌ 無法開啟攝影機")
    #     return


    # reader = RTSPReader(RTSPReaderConfig(url=DEVICE_CAMERA0, drop_grab_n=2))
    reader = RTSPReader(RTSPReaderConfig(url=RTSP_URL_STREAM1, drop_grab_n=2))
    reader.start()


    # 設定 Callback
    window_name = "YOLO11n - Camera"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_click)

    # 上一幀的時間，計算幀率用
    prev_time = 0

    # 追蹤歷史
    track_history = {}  # {id: (cx, cy)}
    # 追蹤延遲刪除軌跡
    disappear_counter = {}  # {id: 次數}

    # 每個 ID 上一幀在哪個區域
    last_zone = {}   # {id: "door" / "inside" / "none"}
    # 上一幀「綠色區域」總共有幾個人
    prev_inside_count = 0

    # 通知冷卻
    last_notify_ts = 0.0
    notify_cooldown = 10

    try:
        while True:
            
            # ret, frame = cap.retrieve()
            # ret, frame = cap.read()
            # h, w = frame.shape[:2]
            # print(f"📏 畫面大小：{w} x {h}")
            # if not ret:
            #     print("❌ 無法讀取影像")
            #     break

            frame, ts = reader.get_latest()
            if frame is None:
                # 還在連線
                cv2.waitKey(1)
                continue

            # 鏡像
            frame = cv2.flip(frame, 1)

            # 計算 fps
            current_time = time.time()
            fps = 1 / (current_time - prev_time) if prev_time != 0 else 0
            prev_time = current_time

            # 用 YOLO 做推論
            # {0: persion, 39: bottle, 47: apple, 49: orange, 67: cell phone}
            results = model.track(  # 追蹤
                frame,
                tracker=TRACKER_BYTETRACK_PATH,
                persist=True,
                # classes=[0]
                conf=0.5,
                iou=0.6,
                classes=[47, 49]
            )

            r = results[0]

            # 繪製偵測結果
            annotated_frame = r.plot()

            # 錄影
            recording_worker.update(raw_frame=frame)

            # 紀錄當前在店內的 ids
            inside_now_ids = set()

            # 若有追蹤到物件
            if r.boxes.id is not None:
                ids = r.boxes.id.int().cpu().tolist()
                boxes = r.boxes.xywh.cpu().tolist()

                current_ids = set(ids)  # 當前畫面還活著的 ID

                for old_id in list(track_history.keys()):  # 3幀緩衝清除
                    if old_id not in current_ids:
                        disappear_counter[old_id] = disappear_counter.get(
                            old_id, 0) + 1

                        # 若消失超過 3 幀 → 刪除
                        if disappear_counter[old_id] > 3:
                            track_history.pop(old_id, None)
                            disappear_counter.pop(old_id, None)
                            last_zone.pop(old_id, None)
                    else:
                        # 如果 ID 存在 → reset counter
                        disappear_counter[old_id] = 0

                # 追蹤軌跡、ROI 判斷
                for obj_id, (cx, cy, w, h) in zip(ids, boxes):

                    cx, cy = int(cx), int(cy)

                    # 判斷這一幀在哪個區域
                    in_door = cv2.pointPolygonTest(
                        ENTRY_ROI_PTS,  (cx, cy), False) >= 0
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

                    # ===== 通知條件：上一幀綠區沒人 + 這個人第一次踏進綠區 =====
                    if (current_time - last_notify_ts > notify_cooldown
                            and prev_inside_count == 0
                            and zone_prev == "door"
                            and zone_now == "inside"):
                        # print(f"🔔 ID {obj_id} 從紅區/外面進到綠區，且之前綠區沒人 → 發通知")
                        # if Doing:
                        #     Doing = False

                        last_notify_ts = current_time  # 通知冷卻

                        # 複製一份新的給 Thread 使用
                        snap = annotated_frame.copy()

                        def notify_job():
                            # 1) 語音提醒
                            play_alert_async(times=1, audio_path=AUDIO_ALERT_PATH)

                            # 2) resize + encode
                            resize_frame = cv2.resize(snap, (960, 540))
                            ok, buf = cv2.imencode(".jpg", resize_frame)
                            if not ok:
                                print("⚠️ cv2.imencode failed")
                                # return

                            # 3) Cloudflare R2 存檔
                            key = make_datetime_key(ext=".jpg")
                            try:
                                url = r2.upload_bytes(
                                    buf.tobytes(),
                                    key=key,
                                    content_type="image/jpeg"
                                )
                            except Exception as e:
                                print("⚠️ r2 upload failed", e)
                                url = None

                            # 4) LINE push
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            try:
                                push_message(
                                    cfg=line_cfg,
                                    msg=f"推播測試 {now_str}",
                                    img_url=url,
                                )
                            except Exception as e:
                                print("⚠️ line push message failed", e)

                        accepted = worker.submit(notify_job)
                        if not accepted:
                            print("⚠️ notify job dropped (queue full)")

                        cv2.putText(
                            img=annotated_frame,
                            text="Notify",
                            org=(1650, 30),
                            fontFace=cv2.FONT_HERSHEY_DUPLEX,  # 字體樣式
                            fontScale=1,  # 字體倍數
                            color=(35, 0, 255),
                            thickness=2  # 字體粗細
                        )

                    # 更新這個 ID 的區域狀態
                    last_zone[obj_id] = zone_now

                    # 建立軌跡歷史
                    if obj_id not in track_history:
                        track_history[obj_id] = []

                    track_history[obj_id].append((cx, cy))

                    # 限制軌跡長度，避免太長
                    if len(track_history[obj_id]) > 20:
                        track_history[obj_id] = track_history[obj_id][-20:]

                    # 畫軌跡線
                    if len(track_history[obj_id]) >= 2:
                        for i in range(1, len(track_history[obj_id])):
                            cv2.line(
                                img=annotated_frame,
                                pt1=track_history[obj_id][i - 1],
                                pt2=track_history[obj_id][i],
                                color=(0, 255, 0),  # 綠色
                                thickness=2,
                            )

                    # 畫中心點
                    cv2.circle(
                        img=annotated_frame,
                        center=(cx, cy),
                        radius=5,
                        color=(252, 0, 168),
                        thickness=2
                    )

            # 更新「這一幀」的綠區人數，給下一幀用
            now_inside_count = len(inside_now_ids)
            prev_inside_count = now_inside_count

            # FPS 顯示
            cv2.putText(
                img=annotated_frame,
                text=f"FPS: {int(fps)}",
                org=(10, 30),
                fontFace=cv2.FONT_HERSHEY_DUPLEX,  # 字體樣式
                fontScale=1,  # 字體倍數
                color=(35, 255, 150),
                thickness=2  # 字體粗細
            )

            # ROI 多邊形
            cv2.polylines(
                img=annotated_frame,
                pts=[ENTRY_ROI_PTS],
                isClosed=True,
                color=(0, 0, 255),
                thickness=5
            )

            cv2.polylines(
                img=annotated_frame,
                pts=[INSIDE_ROI_PTS],
                isClosed=True,
                color=(0, 255, 0),
                thickness=5
            )

            # 顯示畫面
            cv2.imshow(window_name, annotated_frame)

            # 按 q 離開
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break 
    finally:
        # 追蹤歷史
        print(track_history)
        # 追蹤延遲刪除軌跡
        print(disappear_counter)
        # 每個 ID 上一幀在哪個區域
        print(last_zone)

        for fn in [
            reader.stop,
            recording_worker.stop,
            rec.stop,
            cv2.destroyAllWindows,
        ]:
            try:
                fn()
            except Exception as e:
                print("cleanup error:", e)


if __name__ == "__main__":
    main()

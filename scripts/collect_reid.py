import cv2
import os
import time
from datetime import datetime
from ultralytics import YOLO
from dotenv import load_dotenv

load_dotenv()

RTSP_BASE = os.getenv("RTSP_URL_STREAM2")
YOLO11_MODEL_M_PATH = os.getenv("YOLO11_MODEL_M_PATH")

# 可調參數（少量優化重點都集中在這）
DROP_GRAB_N = 2            # 丟幾張舊影格（你原本是 2）
RECONNECT_SEC = 2.0        # 斷線後重連等待
READ_FAIL_LIMIT = 30       # 連續失敗幾次後重連
SAVE_EVERY_N_FRAMES = 5  # 每 5 幀存一次，避免爆量
SHOW_WINDOW = "camera"
OBJECT_NAME = "orange-1216"


def open_cap(rtsp_url: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    # 有些版本不吃，但留著沒壞處
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def build_rtsp_url(base: str) -> str:
    # 如果 base 已經有 '?', 就用 '&'，不然用 '?'
    sep = '&' if '?' in base else '?'
    # tcp 通常比 udp 穩；stimeout 讓它不要卡死太久（單位 us，這邊 3 秒）
    return f"{base}{sep}rtsp_transport=tcp&stimeout=3000000"


def main():
    save_root = f"datasets/{OBJECT_NAME}"
    os.makedirs(save_root, exist_ok=True)

    model = YOLO(YOLO11_MODEL_M_PATH)

    # 可能降低抖動（視環境而定）
    try:
        cv2.setNumThreads(1)
    except Exception:
        pass

    if not RTSP_BASE:
        print("❌ 環境變數 RTSP_URL_STREAM1 沒有設定")
        return

    rtsp_url = build_rtsp_url(RTSP_BASE)

    cap = None
    fail_count = 0  # 失敗次數

    # 簡單 FPS 觀測
    last_t = time.time()
    frame_count = 0

    # 截圖 frame
    frame_idx = 0

    while True:
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            print("🔄 重新連線中...")
            cap = open_cap(rtsp_url)
            if not cap.isOpened():
                print("❌ 連線失敗，稍後重試")
                time.sleep(RECONNECT_SEC)
                continue
            fail_count = 0
            print("✅ 連線成功")

        # 丟掉舊影格，降低延遲
        for _ in range(DROP_GRAB_N):
            cap.grab()

        t0 = time.time()
        ret, frame = cap.read()
        dt = (time.time() - t0) * 1000.0

        if not ret or frame is None:
            fail_count += 1
            if fail_count % 5 == 0:
                print(f"⚠️ read 失敗 {fail_count} 次（最近一次 read 耗時 {dt:.1f} ms）")
            if fail_count >= READ_FAIL_LIMIT:
                print("🧯 連續失敗過多，釋放並重連")
                cap.release()
                cap = None
                time.sleep(RECONNECT_SEC)
            continue
        fail_count = 0

        frame = cv2.flip(frame, 1)
        frame_idx += 1

        # fps 顯示
        frame_count += 1
        now = time.time()
        if now - last_t >= 1.0:
            fps = frame_count / (now - last_t)
            print(f"📈 FPS ~ {fps:.1f} | read {dt:.1f} ms | drop={DROP_GRAB_N}")
            last_t = now
            frame_count = 0

        # YOLO 偵測人
        results = model(frame, classes=[49])  # 0: person, 47: apple, 49: orange,
        r = results[0]

        annotated = frame.copy()

        if r.boxes is not None and len(r.boxes) > 0:
            boxes = r.boxes.xyxy.cpu().tolist()

            for i, (x1, y1, x2, y2) in enumerate(boxes):
                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

                # 避免奇怪的框
                if x2 <= x1 or y2 <= y1:
                    continue

                person_crop = frame[y1:y2, x1:x2]

                # 可選：resize 成 ReID 常用大小（例如 256x128 / 128x256）
                person_crop = cv2.resize(person_crop, (128, 256))

                # 控制存檔頻率
                if frame_idx % SAVE_EVERY_N_FRAMES == 0:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = os.path.join(save_root, f"{ts}_id{i}.jpg")
                    cv2.imwrite(filename, person_crop)
                    print("💾 已存檔:", filename)
                    frame_idx = 0

                # 畫框方便你看
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # # FPS 顯示
        # cv2.putText(
        #     img=annotated,
        #     text=f"FPS: {int(fps)}",
        #     org=(1800, 30),
        #     fontFace=cv2.FONT_HERSHEY_DUPLEX,  # 字體樣式
        #     fontScale=1,  # 字體倍數
        #     color=(35, 255, 150),
        #     thickness=2  # 字體粗細
        # )

        cv2.putText(
            img=annotated,
            text=f"Collecting for: {OBJECT_NAME}",
            org=(10, 30),
            fontFace=cv2.FONT_HERSHEY_DUPLEX,
            fontScale=1,
            color=(0, 0, 0),
            thickness=2
        )

        # 顯示畫面
        cv2.imshow("ReID Collector", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

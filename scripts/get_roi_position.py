import cv2
import numpy as np

# 門口多邊形區域
ENTRY_ROI = np.array([
    (1, 601),
    (439, 701),
    (659, 1001),
    (999, 1201),
    (1399, 1201),
    (1449, 1296),
    (1, 1296),
], np.int32)

ENTRY_ROI_PTS = ENTRY_ROI.reshape((-1, 1, 2))

# 店內多邊形區域
INSIDE_ROI = np.array([
    (1, 600),
    (1, 1),
    (2304, 1),
    (2304, 1296),
    (1450, 1296),
    (1400, 1200),
    (1000, 1200),
    (660, 1000),
    (440, 700),
], np.int32)

INSIDE_ROI_PTS = INSIDE_ROI.reshape((-1, 1, 2))

# 全域變數存點
points = []
histories = []
window_name = "Image"
polygon_closed = False


def on_click(event, x, y, flags, param):
    global points, img, temp_img

    # 左鍵按下：新增一個頂點
    if event == cv2.EVENT_LBUTTONDOWN and not polygon_closed:
        points.append((x, y))
        # 每次畫在 temp_img 上
        cv2.circle(temp_img, (x, y), 5, (0, 255, 0), -1)

        # 若有兩個以上點就畫線
        if len(points) > 1:
            cv2.line(temp_img, points[-2], points[-1], (0, 255, 0), 2)

        histories.append(temp_img.copy())
        cv2.imshow(window_name, temp_img)


def main():
    global points, img, temp_img, polygon_closed

    img = cv2.imread("assets/photos/draw_roi.jpg")
    height, width = img.shape[:2]
    if img is None:
        print("❌ 找不到圖片 draw_roi.jpg")
        return

    # 用一張 temp_img 來畫，不改到原圖
    temp_img = img.copy()
    histories.append(img.copy())

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, width, height)
    cv2.setMouseCallback(window_name, on_click)

    while True:
        cv2.imshow(window_name, temp_img)
        key = cv2.waitKey(20) & 0xFF
        # ROI
        cv2.polylines(
            img=temp_img,
            pts=[ENTRY_ROI_PTS],
            isClosed=True,
            color=(0, 0, 255),
            thickness=5,
        )
        cv2.polylines(
            img=temp_img,
            pts=[INSIDE_ROI_PTS],
            isClosed=True,
            color=(255, 0, 0),
            thickness=5,
        )

        # 按 c：關閉多邊形（連回第一點）
        if key == ord('c'):
            if len(points) >= 3:
                if not polygon_closed:
                    histories.append(temp_img.copy())
                    cv2.line(temp_img, points[-1], points[0], (0, 255, 0), 2)
                    cv2.imshow(window_name, temp_img)
                    print("✅ Polygon 關閉完成")
                    polygon_closed = True
            else:
                print("⚠️ 點至少 3 個點才可以關閉多邊形")

        # 按 r：重設
        elif key == ord('r'):
            points.clear()
            histories.clear()
            temp_img = img.copy()
            histories.append(temp_img.copy())
            polygon_closed = False
            print("🔄 重設所有點")

        # 按 b：回到上一點
        elif key == ord('b'):
            # 這個邏輯處理是因為 close 的時候是第一點直接連接最後一點（會少一個點），導致引響pop流程。
            # 因此相連後第一次 b 就是只回到沒 c 的狀態
            if polygon_closed:
                polygon_closed = False
            else:
                if len(points) > 0:
                    points.pop()

            if len(histories) > 1:
                histories.pop()
            temp_img = histories[-1].copy()

            cv2.imshow(window_name, temp_img)
            print("⏮️ 回到前一點")

        # 按 q：離開，印出座標
        elif key == ord('q'):
            break
    
    cv2.destroyAllWindows()

    if points:
        roi = np.array(points, dtype=np.int32)
        print("📌 你的 ROI 點如下：")
        print(roi)
        # 之後可以這樣用：
        # ENTRY_ROI = roi
    else:
        print("沒有選任何點，程式結束。")


if __name__ == "__main__":
    main()

# debug_yolo.py
from modules.settings import get_settings
from modules.yolo_runtime import YoloRuntime
from modules.shop_state_manager import shop_state_manager

if __name__ == "__main__":
    settings = get_settings()

    # Debug 模式：主執行緒直接跑 loop + 開視窗
    runtime = YoloRuntime(
        settings=settings,
        shop_state_manager=shop_state_manager,
        show_window=True,     # ✅ 要顯示視窗
        run_in_thread=False,  # ✅ 不開 thread，_loop 在 main thread 跑
    )

    try:
        runtime.start()       # 這裡會卡住，直到你在 GUI 裡按 q
    finally:
        runtime.stop()

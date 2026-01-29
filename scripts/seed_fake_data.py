#!/usr/bin/env python3
"""
生成 30 天假訪客資料用於測試 Dashboard
"""

import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
from datetime import datetime, timedelta
from modules.storage.visitor_db import visitor_db

# 設定隨機種子以便重現
random.seed(42)

# 每小時權重（模擬真實店鋪流量）
HOUR_WEIGHTS = {
    9: 0.3,   # 開店
    10: 0.6,
    11: 0.9,  # 午前高峰
    12: 0.7,
    13: 0.5,
    14: 0.8,
    15: 1.0,  # 下午高峰
    16: 0.9,
    17: 0.7,
    18: 0.4,
    19: 0.2,  # 接近打烊
}

# 星期權重（0=週一）
WEEKDAY_WEIGHTS = {
    0: 0.7,   # 週一
    1: 0.8,   # 週二
    2: 0.9,   # 週三
    3: 0.85,  # 週四
    4: 1.0,   # 週五
    5: 1.2,   # 週六（最高）
    6: 0.6,   # 週日
}


def generate_fake_data(days: int = 30, base_daily_visitors: int = 25):
    """
    生成假訪客資料

    Args:
        days: 生成天數
        base_daily_visitors: 基準每日訪客數
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_entries = 0

    print(f"開始生成 {days} 天的假資料...")
    print(f"基準每日訪客數: {base_daily_visitors}")
    print("-" * 50)

    for day_offset in range(days - 1, -1, -1):  # 從最早的日期開始
        target_date = today - timedelta(days=day_offset)
        weekday = target_date.weekday()

        # 計算當天訪客數（加入隨機波動）
        weekday_factor = WEEKDAY_WEIGHTS.get(weekday, 0.8)
        random_factor = random.uniform(0.7, 1.3)
        daily_count = int(base_daily_visitors * weekday_factor * random_factor)

        # 在營業時間內分配訪客
        entries_today = 0
        for hour, weight in HOUR_WEIGHTS.items():
            # 根據權重決定該小時的訪客數
            hour_count = int(daily_count * weight / sum(HOUR_WEIGHTS.values()) * random.uniform(0.5, 1.5))

            for _ in range(hour_count):
                # 在該小時內隨機分布
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                entry_time = target_date.replace(hour=hour, minute=minute, second=second)

                visitor_db.record_entry(entry_time)
                entries_today += 1

        total_entries += entries_today
        weekday_name = ['一', '二', '三', '四', '五', '六', '日'][weekday]
        print(f"  {target_date.strftime('%Y-%m-%d')} (週{weekday_name}): {entries_today} 位訪客")

    print("-" * 50)
    print(f"完成！總共插入 {total_entries} 筆記錄")

    # 顯示統計摘要
    summary = visitor_db.get_summary(days)
    print(f"\n統計摘要:")
    print(f"  期間總訪客: {summary['total_visits']}")
    print(f"  日均訪客: {summary['avg_daily_visits']}")
    if summary['peak_day']:
        print(f"  尖峰日期: {summary['peak_day']['date']} ({summary['peak_day']['count']} 人)")
    if summary['peak_hour']:
        print(f"  尖峰時段: {summary['peak_hour']['hour']}:00")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成假訪客資料")
    parser.add_argument("--days", type=int, default=30, help="生成天數 (預設: 30)")
    parser.add_argument("--base", type=int, default=25, help="基準每日訪客數 (預設: 25)")
    parser.add_argument("--clear", action="store_true", help="先清除現有資料")

    args = parser.parse_args()

    if args.clear:
        print("清除現有資料...")
        with visitor_db._get_conn() as conn:
            conn.execute("DELETE FROM visitor_entries")
            conn.execute("DELETE FROM daily_stats")
            conn.commit()
        print("已清除\n")

    generate_fake_data(days=args.days, base_daily_visitors=args.base)

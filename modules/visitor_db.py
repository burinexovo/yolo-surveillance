# modules/visitor_db.py
from __future__ import annotations

import sqlite3
import threading
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "visitors.db"


@dataclass
class HourlyData:
    hour: int
    count: int


@dataclass
class DailyData:
    date: str
    count: int


@dataclass
class EntryRecord:
    id: int
    entry_time: datetime


class VisitorDB:
    """
    SQLite 訪客記錄資料庫管理器
    - Thread-safe 連線池
    - 自動初始化 schema
    - 提供查詢 API
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._local = threading.local()
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self) -> None:
        """確保資料庫目錄存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_conn(self):
        """取得 thread-local 的資料庫連線"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise

    def _init_schema(self) -> None:
        """初始化資料表"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS visitor_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_visits INTEGER DEFAULT 0,
                    first_entry_time TEXT,
                    last_entry_time TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_entry_time
                    ON visitor_entries(entry_time);
            """)
            conn.commit()

    # === 寫入 API ===

    def record_entry(self, entry_time: Optional[datetime] = None) -> int:
        """記錄一次入店事件，回傳插入的 id"""
        ts = entry_time or datetime.now()
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO visitor_entries (entry_time) VALUES (?)",
                (ts.isoformat(),)
            )
            conn.commit()

            # 同步更新 daily_stats
            self._update_daily_stats(conn, ts)

            return cur.lastrowid

    def _update_daily_stats(self, conn: sqlite3.Connection, ts: datetime) -> None:
        """更新每日統計快取"""
        date_str = ts.strftime("%Y-%m-%d")
        time_str = ts.strftime("%H:%M:%S")

        conn.execute("""
            INSERT INTO daily_stats (date, total_visits, first_entry_time, last_entry_time)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_visits = total_visits + 1,
                last_entry_time = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (date_str, time_str, time_str, time_str))
        conn.commit()

    # === 查詢 API ===

    def get_today_visits(self) -> int:
        """取得今日訪客數"""
        today = date.today().isoformat()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT total_visits FROM daily_stats WHERE date = ?",
                (today,)
            ).fetchone()
            return row["total_visits"] if row else 0

    def get_hourly_distribution(self, target_date: Optional[date] = None) -> List[HourlyData]:
        """取得指定日期的每小時分布"""
        target = target_date or date.today()
        start = datetime.combine(target, datetime.min.time())
        end = start + timedelta(days=1)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT strftime('%H', entry_time) as hour, COUNT(*) as count
                FROM visitor_entries
                WHERE entry_time >= ? AND entry_time < ?
                GROUP BY hour
                ORDER BY hour
            """, (start.isoformat(), end.isoformat())).fetchall()

        # 填充完整 24 小時
        hour_map = {int(r["hour"]): r["count"] for r in rows}
        return [HourlyData(hour=h, count=hour_map.get(h, 0)) for h in range(24)]

    def get_daily_trend(self, days: int = 7) -> List[DailyData]:
        """取得最近 N 天的每日訪客數"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT date, total_visits as count
                FROM daily_stats
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """, (start_date.isoformat(), end_date.isoformat())).fetchall()

        # 填充缺失的日期
        date_map = {r["date"]: r["count"] for r in rows}
        result = []
        current = start_date
        while current <= end_date:
            d_str = current.isoformat()
            result.append(DailyData(date=d_str, count=date_map.get(d_str, 0)))
            current += timedelta(days=1)

        return result

    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        """取得統計摘要"""
        daily_data = self.get_daily_trend(days)
        total = sum(d.count for d in daily_data)
        avg = total / len(daily_data) if daily_data else 0

        peak_day = max(daily_data, key=lambda d: d.count) if daily_data else None

        # 計算尖峰小時（需要額外查詢）
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT strftime('%H', entry_time) as hour, COUNT(*) as count
                FROM visitor_entries
                WHERE date(entry_time) >= ? AND date(entry_time) <= ?
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 1
            """, (start_date.isoformat(), end_date.isoformat())).fetchone()

        peak_hour = {"hour": int(row["hour"]), "avg_count": row["count"] / days} if row else None

        return {
            "total_visits": total,
            "avg_daily_visits": round(avg, 1),
            "peak_day": {"date": peak_day.date, "count": peak_day.count} if peak_day else None,
            "peak_hour": peak_hour,
        }

    def get_entries_by_date(self, target_date: date) -> List[EntryRecord]:
        """取得指定日期的所有入店事件"""
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT id, entry_time
                FROM visitor_entries
                WHERE entry_time >= ? AND entry_time < ?
                ORDER BY entry_time
            """, (start.isoformat(), end.isoformat())).fetchall()

        return [
            EntryRecord(
                id=row["id"],
                entry_time=datetime.fromisoformat(row["entry_time"])
            )
            for row in rows
        ]


# 全域單例
visitor_db = VisitorDB()

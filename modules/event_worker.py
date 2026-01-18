# modules/event_worker.py
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerConfig:
    max_queue: int = 20          # 避免事件塞爆 RAM
    drop_if_full: bool = True    # 滿了就丟掉（不阻塞主迴圈）
    name: str = "EventWorker"


class EventWorker:
    def __init__(self, cfg: WorkerConfig = WorkerConfig()):
        self.cfg = cfg
        self._q: queue.Queue[Callable[[], None]
                             ] = queue.Queue(maxsize=cfg.max_queue)
        self._stop = threading.Event()
        self._t = threading.Thread(
            target=self._loop, name=cfg.name, daemon=True)
        self._t.start()

    def submit(self, fn: Callable[[], None]) -> bool:
        """回傳 True=成功排入，False=queue 滿被丟棄"""
        if self._stop.is_set():
            return False
        try:
            if self.cfg.drop_if_full:
                self._q.put_nowait(fn)
            else:
                self._q.put(fn)  # 可能阻塞（不建議在主迴圈用）
            return True
        except queue.Full:
            return False

    def _loop(self):
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                job()
            except Exception as e:
                logger.exception("%s job failed", self.cfg.name)
            finally:
                self._q.task_done()

    def stop(self, drain: bool = False):
        """drain=True 會等 queue 清空再停；False 直接停"""
        if drain:
            self._q.join()
        self._stop.set()

# -*- coding: utf-8 -*-
"""数据引擎 — 后台线程调用 token_meter 数据层

在 QThread 中执行耗时的数据扫描与聚合，通过 Qt Signal 通知主线程更新 UI。
带本地缓存：第二次启动立刻显示缓存数据，后台再跑全量更新。
"""

import json
import os
import time
import traceback

from PySide6.QtCore import QThread, Signal, QMutex


CACHE_PATH = os.path.join(
    os.path.expanduser("~"), ".token-meter-desktop", "cache.json"
)


def _save_cache(data: dict):
    """把数据存到缓存文件"""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _load_cache() -> dict | None:
    """读缓存"""
    try:
        if not os.path.exists(CACHE_PATH):
            return None
        mtime = os.path.getmtime(CACHE_PATH)
        if time.time() - mtime > 7 * 24 * 3600:  # 缓存超过 7 天丢弃
            return None
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class DataEngine(QThread):
    """后台数据采集线程

    Signals:
        data_ready(dict): 数据加载完成，包含 {"cross": ..., "logs": ..., "from_cache": bool}
        error(str): 数据加载出错
    """

    data_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._running = False

    def refresh(self):
        """请求刷新数据（如果当前未在运行）"""
        self._mutex.lock()
        running = self._running
        self._mutex.unlock()
        if not running:
            self.start()

    def run(self):
        """执行数据采集（在后台线程中运行）"""
        self._mutex.lock()
        self._running = True
        self._mutex.unlock()

        try:
            from token_meter import app

            # 1. 先读缓存，立刻显示（增量：不用等全量扫描）
            cached = _load_cache()
            if cached:
                cached["from_cache"] = True
                self.data_ready.emit(cached)

            # 2. 后台跑全量聚合
            sources = app.all_session_sources()
            cross = app.cross_session(sources=sources)
            logs = app.log_sessions_state()

            result = {"cross": cross, "logs": logs, "from_cache": False}

            # 3. 存缓存
            _save_cache(result)

            # 4. 发射最新数据
            self.data_ready.emit(result)

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")

        finally:
            self._mutex.lock()
            self._running = False
            self._mutex.unlock()

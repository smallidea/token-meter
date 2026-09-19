# -*- coding: utf-8 -*-
"""数据引擎 — 后台线程调用 token_meter 数据层

在 QThread 中执行耗时的数据扫描与聚合，通过 Qt Signal 通知主线程更新 UI。
"""

import time
import traceback

from PySide6.QtCore import QThread, Signal, QMutex


class DataEngine(QThread):
    """后台数据采集线程

    Signals:
        data_ready(dict): 数据加载完成，包含 {"cross": ..., "logs": ...}
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

            # 首次调用获取所有会话源并计算聚合（在后台子线程运行，不阻塞UI）
            sources = app.all_session_sources()
            cross = app.cross_session(sources=sources)
            logs = app.log_sessions_state()

            self.data_ready.emit({
                "cross": cross,
                "logs": logs,
            })

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")

        finally:
            self._mutex.lock()
            self._running = False
            self._mutex.unlock()

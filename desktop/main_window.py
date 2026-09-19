# -*- coding: utf-8 -*-
"""Token Meter 桌面端主窗口

包含 QTabWidget 标签页容器、系统托盘图标和定时刷新逻辑。
"""

import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QSystemTrayIcon, QMenu,
    QStatusBar, QLabel, QApplication,
)

from desktop.data_engine import DataEngine
from desktop.tabs.overview_tab import OverviewTab
from desktop.tabs.sessions_tab import SessionsTab
from desktop.tabs.models_tab import ModelsTab
from desktop.tabs.daily_tab import DailyTab


# 全局深色样式表
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #07090c;
    color: #f6f8fb;
    font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.075);
    border-radius: 8px;
    background: #0d1117;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #a8b3c1;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 13px;
    margin: 2px 1px;
}
QTabBar::tab:hover {
    background: rgba(255, 255, 255, 0.045);
    color: #f6f8fb;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 0.08);
    color: #f6f8fb;
}
QTableView {
    background-color: #111820;
    alternate-background-color: #17212b;
    border: 1px solid rgba(255, 255, 255, 0.075);
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.05);
    selection-background-color: rgba(0, 188, 235, 0.2);
    selection-color: #f6f8fb;
    color: #f6f8fb;
    font-size: 12px;
}
QTableView::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background: #17212b;
    color: #a8b3c1;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 6px 8px;
    font-weight: bold;
    font-size: 11px;
    text-transform: uppercase;
}
QComboBox {
    background: #111820;
    color: #f6f8fb;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 140px;
    font-size: 12px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #17212b;
    color: #f6f8fb;
    selection-background-color: rgba(0, 188, 235, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
QLineEdit {
    background: #111820;
    color: #f6f8fb;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}
QStatusBar {
    background: #07090c;
    color: #7d8ba0;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
}
QScrollBar:vertical {
    background: #0d1117;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class MainWindow(QMainWindow):
    """Token Meter 桌面端主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Token Meter")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 900)
        self.setStyleSheet(DARK_STYLESHEET)

        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 创建标签页
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self.setCentralWidget(self._tabs)

        self._overview = OverviewTab()
        self._sessions = SessionsTab()
        self._models = ModelsTab()
        self._daily = DailyTab()

        self._tabs.addTab(self._overview, "概览")
        self._tabs.addTab(self._sessions, "会话")
        self._tabs.addTab(self._models, "模型")
        self._tabs.addTab(self._daily, "花费")

        # 状态栏
        self._status_label = QLabel("正在加载数据...")
        self.statusBar().addPermanentWidget(self._status_label)

        # 数据引擎
        self._engine = DataEngine()
        self._engine.data_ready.connect(self._on_data_ready)
        self._engine.error.connect(self._on_error)

        # 定时刷新（60秒）
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._engine.refresh)
        self._refresh_timer.start(60_000)

        # 系统托盘
        self._setup_tray()

        # 首次加载
        self._engine.refresh()

    def _setup_tray(self):
        """初始化系统托盘图标"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.svg")
        if os.path.exists(icon_path):
            self._tray.setIcon(QIcon(icon_path))
        else:
            self._tray.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))
        self._tray.setToolTip("Token Meter")

        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        refresh_action = QAction("立即刷新", self)
        refresh_action.triggered.connect(self._engine.refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _show_window(self):
        """从托盘恢复窗口"""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason):
        """托盘图标双击时显示窗口"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _on_data_ready(self, data: dict):
        """数据加载完成，更新所有标签页"""
        cross = data.get("cross", {})
        total = cross.get("total_sessions", 0)
        cost = cross.get("total_cost", 0)
        ts = cross.get("generated_at")

        import datetime
        if ts:
            t = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            self._status_label.setText(
                f"共 {total} 个会话 · 总花费 ${cost:.2f} · 更新于 {t}"
            )
        else:
            self._status_label.setText(f"共 {total} 个会话 · 总花费 ${cost:.2f}")

        # 分发到各标签页
        self._overview.update_data(data)
        self._sessions.update_data(data)
        self._models.update_data(data)
        self._daily.update_data(data)

    def _on_error(self, msg: str):
        """数据加载出错"""
        self._status_label.setText(f"错误: {msg}")

    def closeEvent(self, event):
        """关闭窗口时最小化到托盘（如果有托盘的话）"""
        if hasattr(self, '_tray') and self._tray.isVisible():
            self.hide()
            self._tray.showMessage(
                "Token Meter",
                "已最小化到系统托盘，双击图标恢复。",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
        else:
            event.accept()

    def force_quit(self):
        """强制退出（不最小化到托盘）"""
        if hasattr(self, '_tray'):
            self._tray.hide()
        QApplication.quit()

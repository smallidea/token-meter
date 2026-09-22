# -*- coding: utf-8 -*-
"""Token Meter 桌面端主窗口

包含 QTabWidget 标签页容器、系统托盘图标、快捷键支持与高质感深色主题。
"""

import os
import sys
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QSystemTrayIcon, QMenu,
    QStatusBar, QLabel, QPushButton, QWidget, QHBoxLayout,
    QApplication,
)

from desktop.data_engine import DataEngine
from desktop.tabs.overview_tab import OverviewTab
from desktop.tabs.sessions_tab import SessionsTab
from desktop.tabs.models_tab import ModelsTab
from desktop.tabs.tools_tab import ToolsTab
from desktop.tabs.daily_tab import DailyTab


# 统一现代深色设计系统样式表（Fluent / GitHub Dark 质感）
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #07090c;
    color: #f6f8fb;
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei", -apple-system, sans-serif;
    font-size: 13px;
}

/* 标签容器与药丸胶囊 TabBar */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: #0d1117;
    top: 4px;
}
QTabBar {
    qproperty-drawBase: 0;
    background: transparent;
    margin-left: 12px;
    margin-top: 4px;
}
QTabBar::tab {
    background: rgba(255, 255, 255, 0.03);
    color: #a8b3c1;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 13px;
    margin-right: 6px;
    margin-bottom: 2px;
}
QTabBar::tab:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #f6f8fb;
    border-color: rgba(255, 255, 255, 0.12);
}
QTabBar::tab:selected {
    background: rgba(0, 188, 235, 0.14);
    color: #00bceb;
    border: 1px solid rgba(0, 188, 235, 0.45);
}

/* 表格全局质感 */
QTableView {
    background-color: #111820;
    alternate-background-color: #141e28;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.04);
    selection-background-color: rgba(0, 188, 235, 0.22);
    selection-color: #f6f8fb;
    color: #f6f8fb;
    font-size: 12px;
    outline: none;
}
QTableView::item {
    padding: 6px 10px;
    border: none;
}
QTableView::item:hover {
    background-color: rgba(0, 188, 235, 0.08);
}
QHeaderView::section {
    background: #17212b;
    color: #7d8ba0;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 7px 10px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* 输入框与下拉框 */
QLineEdit {
    background: #111820;
    color: #f6f8fb;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    selection-background-color: #00bceb;
}
QLineEdit:focus {
    border: 1px solid #00bceb;
    background: #151f2b;
}

QComboBox {
    background: #111820;
    color: #f6f8fb;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 5px 12px;
    min-width: 130px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: rgba(255, 255, 255, 0.22);
}
QComboBox:focus {
    border-color: #00bceb;
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
    border-radius: 6px;
    padding: 4px;
}

/* 按钮通用风格 */
QPushButton {
    background: #17212b;
    color: #f6f8fb;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(0, 188, 235, 0.15);
    border-color: #00bceb;
    color: #00bceb;
}
QPushButton:pressed {
    background: rgba(0, 188, 235, 0.25);
}

/* 分割面板 Splitter 抓手美化 */
QSplitter::handle {
    background: rgba(255, 255, 255, 0.05);
}
QSplitter::handle:hover {
    background: rgba(0, 188, 235, 0.4);
}
QSplitter::handle:vertical {
    height: 4px;
    margin: 2px 0;
}
QSplitter::handle:horizontal {
    width: 4px;
    margin: 0 2px;
}

/* 现代极细滚动条 */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.14);
    border-radius: 4px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 188, 235, 0.5);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.14);
    border-radius: 4px;
    min-width: 36px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(0, 188, 235, 0.5);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* 状态栏 */
QStatusBar {
    background: #07090c;
    color: #7d8ba0;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 11.5px;
    padding: 2px 8px;
}
"""


class MainWindow(QMainWindow):
    """Token Meter 桌面端主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Token Meter · AI 编码消耗监控")
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
        self._tools = ToolsTab()
        self._daily = DailyTab()

        self._tabs.addTab(self._overview, " 概览 ")
        self._tabs.addTab(self._sessions, " 会话 ")
        self._tabs.addTab(self._models, " 模型 ")
        self._tabs.addTab(self._tools, " 工具 ")
        self._tabs.addTab(self._daily, " 花费趋势 ")

        # 状态栏组件增强
        self._setup_statusbar()

        # 数据引擎
        self._engine = DataEngine()
        self._engine.data_ready.connect(self._on_data_ready)
        self._engine.error.connect(self._on_error)

        # 定时刷新（60秒）
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_request_refresh)
        self._refresh_timer.start(60_000)

        # 全局快捷键绑定
        self._setup_shortcuts()

        # 系统托盘
        self._setup_tray()

        # 首次加载
        self._on_request_refresh()

    def _setup_statusbar(self):
        """配置增强型状态栏"""
        sb = self.statusBar()

        # 左侧数据汇总信息
        self._status_label = QLabel("正在初始化并加载数据...")
        self._status_label.setStyleSheet("color: #a8b3c1; padding-left: 4px;")
        sb.addWidget(self._status_label, 1)

        # 右侧操作区容器
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 状态指示灯
        self._status_indicator = QLabel("● 就绪")
        self._status_indicator.setStyleSheet("color: #66d990; font-size: 11px; font-weight: bold;")
        right_layout.addWidget(self._status_indicator)

        # 手动刷新按钮
        self._btn_refresh = QPushButton("⟳ 刷新")
        self._btn_refresh.setToolTip("立即重新扫描并刷新数据 (Ctrl+R / F5)")
        self._btn_refresh.setFixedHeight(24)
        self._btn_refresh.setStyleSheet("""
            QPushButton {
                background: #111820;
                color: #a8b3c1;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(0, 188, 235, 0.15);
                color: #00bceb;
                border-color: #00bceb;
            }
        """)
        self._btn_refresh.clicked.connect(self._on_request_refresh)
        right_layout.addWidget(self._btn_refresh)

        # Web 版跳转按钮
        btn_web = QPushButton("网页版 ↗")
        btn_web.setToolTip("在系统默认浏览器中打开 Token Meter Web 仪表盘")
        btn_web.setFixedHeight(24)
        btn_web.setStyleSheet("""
            QPushButton {
                background: #111820;
                color: #7d8ba0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #f6f8fb;
                border-color: rgba(255, 255, 255, 0.2);
            }
        """)
        btn_web.clicked.connect(lambda: webbrowser.open("http://127.0.0.1:8722"))
        right_layout.addWidget(btn_web)

        sb.addPermanentWidget(right_container)

    def _setup_shortcuts(self):
        """配置全局快捷键"""
        # Ctrl+R 或 F5 刷新
        sc_r = QShortcut(QKeySequence("Ctrl+R"), self)
        sc_r.activated.connect(self._on_request_refresh)
        sc_f5 = QShortcut(QKeySequence("F5"), self)
        sc_f5.activated.connect(self._on_request_refresh)

        # Ctrl+F 聚焦会话页搜索
        sc_find = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_find.activated.connect(self._focus_session_search)

    def _focus_session_search(self):
        """切换到会话页并聚焦搜索框"""
        self._tabs.setCurrentIndex(1)
        if hasattr(self._sessions, "edit_search"):
            self._sessions.edit_search.setFocus()
            self._sessions.edit_search.selectAll()

    def _on_request_refresh(self):
        """发起刷新请求并更新状态灯"""
        self._status_indicator.setText("● 同步中...")
        self._status_indicator.setStyleSheet("color: #ffb457; font-size: 11px; font-weight: bold;")
        self._btn_refresh.setEnabled(False)
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
        self._tray.setToolTip("Token Meter · 运行中")

        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        refresh_action = QAction("立即刷新 (Ctrl+R)", self)
        refresh_action.triggered.connect(self._on_request_refresh)
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
        self._btn_refresh.setEnabled(True)
        self._status_indicator.setText("● 已同步")
        self._status_indicator.setStyleSheet("color: #66d990; font-size: 11px; font-weight: bold;")

        cross = data.get("cross", {})
        total = cross.get("total_sessions", 0)
        cost = cross.get("total_cost", 0)
        ts = cross.get("generated_at")

        import datetime
        if ts:
            t = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            self._status_label.setText(
                f"会话总量: {total:,} 个 · 总计花费: ${cost:.2f} · 更新于 {t}"
            )
        else:
            self._status_label.setText(f"会话总量: {total:,} 个 · 总计花费: ${cost:.2f}")

        # 分发到各标签页
        self._overview.update_data(data)
        self._sessions.update_data(data)
        self._models.update_data(data)
        self._tools.update_data(data)
        self._daily.update_data(data)

    def _on_error(self, msg: str):
        """数据加载出错"""
        self._btn_refresh.setEnabled(True)
        self._status_indicator.setText("● 同步失败")
        self._status_indicator.setStyleSheet("color: #ff6f6f; font-size: 11px; font-weight: bold;")
        self._status_label.setText(f"错误: {msg}")

    def closeEvent(self, event):
        """关闭窗口时最小化到托盘（如果有托盘的话）"""
        if hasattr(self, '_tray') and self._tray.isVisible():
            self.hide()
            self._tray.showMessage(
                "Token Meter",
                "已最小化到系统托盘，双击托盘图标即可恢复窗口。",
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

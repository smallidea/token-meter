# -*- coding: utf-8 -*-
"""会话详情模态弹窗

提供对单个会话的深度详情查看：
- 基本元数据（工具/运行时、模型、项目路径、会话 ID）
- 时间与耗时（开始时间、轮次、执行次数）
- Token 详细构成与花费金额（支持对 Cursor 等估算来源做清晰的提示）
- 快捷操作（复制会话 ID、复制项目路径、在文件资源管理器中打开）
"""

import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QWidget,
)


def _fmt_tokens(n) -> str:
    try:
        val = int(n or 0)
        return f"{val:,}"
    except (ValueError, TypeError):
        return str(n)


class SessionDetailDialog(QDialog):
    """会话详情卡片弹窗"""

    def __init__(self, session_data: dict, parent=None):
        super().__init__(parent)
        self._data = session_data or {}
        rt_name = str(self._data.get('runtime') or self._data.get('provider') or 'Token Meter').title()
        self.setWindowTitle(f"会话详情 · {rt_name}")
        self.setMinimumWidth(620)
        self.resize(680, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #f6f8fb;
                font-family: "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei", sans-serif;
            }
            QFrame.detailCard {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 14px;
            }
            QLabel.fieldLabel {
                color: #7d8ba0;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QLabel.fieldValue {
                color: #f6f8fb;
                font-size: 13px;
                font-weight: 500;
            }
            QLabel.fieldValueCode {
                color: #7fdbf2;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px;
            }
            QPushButton.actionBtn {
                background: #17212b;
                color: #a8b3c1;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton.actionBtn:hover {
                background: rgba(0, 188, 235, 0.15);
                border-color: #00bceb;
                color: #f6f8fb;
            }
            QPushButton.actionBtn:pressed {
                background: rgba(0, 188, 235, 0.25);
            }
            QPushButton.primaryBtn {
                background: #00bceb;
                color: #07090c;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton.primaryBtn:hover {
                background: #7fdbf2;
            }
        """)

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. 顶部 Header
        header = QHBoxLayout()
        runtime = str(self._data.get("runtime") or self._data.get("provider") or "未知")
        model = str(self._data.get("model") or "未知")

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel(f"{runtime} 会话")
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #f6f8fb;")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel(f"模型: {model}")
        lbl_sub.setStyleSheet("color: #00bceb; font-size: 13px; font-weight: 600;")
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)

        header.addStretch()

        # 核心花费高亮徽章
        cost = float(self._data.get("cost") or 0.0)
        cost_str = f"${cost:.4f}" if 0 < cost < 0.01 else f"${cost:.2f}"
        badge = QFrame()
        badge.setStyleSheet("""
            QFrame {
                background: rgba(199, 167, 255, 0.12);
                border: 1px solid rgba(199, 167, 255, 0.35);
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(8, 4, 8, 4)
        badge_layout.setSpacing(0)
        lbl_c_title = QLabel("总花费")
        lbl_c_title.setStyleSheet("color: #c7a7ff; font-size: 10px; font-weight: bold; text-align: center;")
        lbl_c_val = QLabel(cost_str)
        lbl_c_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_c_val.setStyleSheet("color: #f6f8fb; text-align: center;")
        badge_layout.addWidget(lbl_c_title, alignment=Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(lbl_c_val, alignment=Qt.AlignmentFlag.AlignCenter)
        header.addWidget(badge)

        main_layout.addLayout(header)

        # 2. 基本信息卡片
        info_card = QFrame()
        info_card.setProperty("class", "detailCard")
        info_grid = QGridLayout(info_card)
        info_grid.setContentsMargins(16, 14, 16, 14)
        info_grid.setHorizontalSpacing(20)
        info_grid.setVerticalSpacing(10)

        # 会话 ID
        sess_id = str(self._data.get("id") or "-")
        info_grid.addWidget(self._make_label("会话 ID", "fieldLabel"), 0, 0)
        lbl_id = QLabel(sess_id)
        lbl_id.setProperty("class", "fieldValueCode")
        lbl_id.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_grid.addWidget(lbl_id, 0, 1)

        btn_copy_id = QPushButton("复制 ID")
        btn_copy_id.setProperty("class", "actionBtn")
        btn_copy_id.clicked.connect(lambda: self._copy_to_clipboard(sess_id, btn_copy_id))
        info_grid.addWidget(btn_copy_id, 0, 2)

        # 项目路径
        project_path = str(self._data.get("project") or "未分类")
        info_grid.addWidget(self._make_label("项目路径", "fieldLabel"), 1, 0)
        lbl_proj = QLabel(project_path)
        lbl_proj.setProperty("class", "fieldValue")
        lbl_proj.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_grid.addWidget(lbl_proj, 1, 1)

        proj_ops = QHBoxLayout()
        proj_ops.setSpacing(6)
        btn_copy_proj = QPushButton("复制路径")
        btn_copy_proj.setProperty("class", "actionBtn")
        btn_copy_proj.clicked.connect(lambda: self._copy_to_clipboard(project_path, btn_copy_proj))
        proj_ops.addWidget(btn_copy_proj)

        btn_open_folder = QPushButton("打开目录")
        btn_open_folder.setProperty("class", "actionBtn")
        btn_open_folder.clicked.connect(lambda: self._open_in_explorer(project_path))
        proj_ops.addWidget(btn_open_folder)
        info_grid.addLayout(proj_ops, 1, 2)

        # 时间与轮次
        started = self._data.get("start") or self._data.get("started") or "-"
        turns = self._data.get("turns", 0)
        info_grid.addWidget(self._make_label("开始时间", "fieldLabel"), 2, 0)
        info_grid.addWidget(self._make_label(str(started), "fieldValue"), 2, 1)

        info_grid.addWidget(self._make_label("交互轮次", "fieldLabel"), 3, 0)
        info_grid.addWidget(self._make_label(f"{turns} 轮", "fieldValue"), 3, 1)

        main_layout.addWidget(info_card)

        # 3. Token 详细数据卡片
        token_card = QFrame()
        token_card.setProperty("class", "detailCard")
        token_layout = QVBoxLayout(token_card)
        token_layout.setContentsMargins(16, 14, 16, 14)
        token_layout.setSpacing(10)

        t_header = QLabel("Token 消耗与分布")
        t_header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t_header.setStyleSheet("color: #f6f8fb;")
        token_layout.addWidget(t_header)

        tokens_tot = int(self._data.get("tokens") or 0)
        tokens_grid = QGridLayout()
        tokens_grid.setHorizontalSpacing(24)
        tokens_grid.setVerticalSpacing(8)

        tokens_grid.addWidget(self._make_label("总 Token", "fieldLabel"), 0, 0)
        lbl_tot = QLabel(_fmt_tokens(tokens_tot))
        lbl_tot.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_tot.setStyleSheet("color: #00bceb;")
        tokens_grid.addWidget(lbl_tot, 0, 1)

        # 如果是 Cursor，显示估算特别说明
        is_cursor = runtime.lower() == "cursor"
        if is_cursor:
            tip_box = QFrame()
            tip_box.setStyleSheet("""
                QFrame {
                    background: rgba(255, 180, 87, 0.08);
                    border: 1px solid rgba(255, 180, 87, 0.3);
                    border-radius: 6px;
                    padding: 8px 12px;
                }
            """)
            tip_layout = QVBoxLayout(tip_box)
            tip_layout.setContentsMargins(0, 0, 0, 0)
            tip_lbl = QLabel(
                "💡 关于 Cursor 计量说明：\n"
                "Cursor 官方未在本地记录 API 实际计量单据，Token Meter 是根据每轮上下文占用与"
                "生成的字符数按每4字符约1 Token 累加估算，且多轮会话为累计消耗（而 Cursor 客户端常显示当前单次上下文），"
                "因此与 Cursor 官方界面的当前上下文或计费请求次数存在口径差异。"
            )
            tip_lbl.setWordWrap(True)
            tip_lbl.setStyleSheet("color: #ffb457; font-size: 11px; line-height: 1.4;")
            tip_layout.addWidget(tip_lbl)
            token_layout.addWidget(tip_box)

        token_layout.addLayout(tokens_grid)
        main_layout.addWidget(token_card)

        main_layout.addStretch()

        # 4. 底部关闭按钮
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setProperty("class", "primaryBtn")
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

    def _make_label(self, text: str, css_class: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", css_class)
        return lbl

    def _copy_to_clipboard(self, text: str, btn: QPushButton):
        """复制文本到剪贴板并给出短暂文字反馈"""
        QGuiApplication.clipboard().setText(text)
        orig_text = btn.text()
        btn.setText("已复制 ✓")
        btn.setEnabled(False)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, lambda: (btn.setText(orig_text), btn.setEnabled(True)))

    def _open_in_explorer(self, folder_path: str):
        """在 Windows 资源管理器中定位/打开文件夹"""
        if not folder_path or folder_path == "未分类":
            return
        if os.path.exists(folder_path):
            if os.path.isdir(folder_path):
                subprocess.Popen(f'explorer "{os.path.normpath(folder_path)}"')
            else:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(folder_path)}"')

# -*- coding: utf-8 -*-
"""概览仪表板标签页

顶部统计卡片 + 模型构成饼图 + 每日花费折线图。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QScrollArea,
)

from desktop.widgets.charts import create_pie_chart, create_line_chart


def _format_tokens(n: int) -> str:
    """格式化 Token 数为可读字符串"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _stat_card(label: str, value: str, accent: bool = False) -> QFrame:
    """创建单个统计卡片"""
    card = QFrame()
    card.setStyleSheet("""
        QFrame {
            background: #111820;
            border: 1px solid rgba(255, 255, 255, 0.075);
            border-radius: 8px;
            padding: 12px;
        }
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(4)

    lbl = QLabel(label)
    lbl.setFont(QFont("Segoe UI", 10))
    lbl.setStyleSheet("color: #a8b3c1; border: none; background: transparent;")
    layout.addWidget(lbl)

    val = QLabel(value)
    val.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
    color = "#00bceb" if accent else "#f6f8fb"
    val.setStyleSheet(f"color: {color}; border: none; background: transparent;")
    val.setObjectName("stat_value")
    layout.addWidget(val)

    return card


class OverviewTab(QWidget):
    """概览仪表板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        # 统计卡片行
        self._cards_layout = QHBoxLayout()
        self._cards_layout.setSpacing(12)
        self._card_cost = _stat_card("总花费", "$0.00", accent=True)
        self._card_tokens = _stat_card("总 Token", "0")
        self._card_sessions = _stat_card("总会话", "0")
        self._card_execs = _stat_card("总执行次数", "0")
        self._cards_layout.addWidget(self._card_cost)
        self._cards_layout.addWidget(self._card_tokens)
        self._cards_layout.addWidget(self._card_sessions)
        self._cards_layout.addWidget(self._card_execs)
        self._layout.addLayout(self._cards_layout)

        # 图表行
        self._charts_layout = QHBoxLayout()
        self._charts_layout.setSpacing(12)
        # 占位
        self._pie_placeholder = QLabel("加载中...")
        self._pie_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pie_placeholder.setStyleSheet("color: #7d8ba0;")
        self._pie_placeholder.setMinimumHeight(350)
        self._line_placeholder = QLabel("加载中...")
        self._line_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._line_placeholder.setStyleSheet("color: #7d8ba0;")
        self._line_placeholder.setMinimumHeight(350)
        self._charts_layout.addWidget(self._pie_placeholder)
        self._charts_layout.addWidget(self._line_placeholder)
        self._layout.addLayout(self._charts_layout)

        self._layout.addStretch()

    def _update_card_value(self, card: QFrame, value: str):
        """更新卡片数值"""
        val_label = card.findChild(QLabel, "stat_value")
        if val_label:
            val_label.setText(value)

    def update_data(self, data: dict):
        """接收完整数据 dict 并更新 UI"""
        cross = data.get("cross", {})

        # 更新统计卡片
        cost = cross.get("total_cost", 0)
        tokens = cross.get("total_tokens", 0)
        sessions = cross.get("total_sessions", 0)
        execs = cross.get("total_executions", 0)

        self._update_card_value(self._card_cost, f"${cost:.2f}")
        self._update_card_value(self._card_tokens, _format_tokens(tokens))
        self._update_card_value(self._card_sessions, str(sessions))
        self._update_card_value(self._card_execs, str(execs))

        # 更新饼图
        model_mix = cross.get("model_mix") or []
        if model_mix:
            pie = create_pie_chart(model_mix, "模型构成", "cost")
            old = self._charts_layout.itemAt(0)
            if old and old.widget():
                old.widget().deleteLater()
            self._charts_layout.insertWidget(0, pie)
            self._pie_placeholder = pie

        # 更新折线图
        daily = cross.get("daily") or []
        if daily:
            line = create_line_chart(daily, "day", "cost", "每日花费趋势", "花费 ($)")
            old = self._charts_layout.itemAt(1)
            if old and old.widget():
                old.widget().deleteLater()
            self._charts_layout.insertWidget(1, line)
            self._line_placeholder = line

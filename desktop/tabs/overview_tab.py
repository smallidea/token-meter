# -*- coding: utf-8 -*-
"""概览仪表板标签页

顶部多维度微质感统计卡片 + 现代化卡片式模型构成饼图 + 每日 Token 趋势折线图。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
)

from desktop.widgets.charts import create_pie_chart, create_line_chart


def _format_tokens(n: int) -> str:
    """格式化 Token 数为中文可读字符串（万/亿）"""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.2f} 亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f} 万"
    return f"{n:,}"


def _stat_card(label: str, value: str, subtext: str = "", accent_color: str = "#00bceb") -> QFrame:
    """创建带顶部导光条与副标的微质感指标卡片"""
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: #111820;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-top: 3px solid {accent_color};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    # 标题
    lbl = QLabel(label)
    lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
    lbl.setStyleSheet("color: #7d8ba0; border: none; background: transparent;")
    layout.addWidget(lbl)

    # 主数值
    val = QLabel(value)
    val.setFont(QFont("Segoe UI Variable Display", 22, QFont.Weight.Bold))
    val.setStyleSheet("color: #f6f8fb; border: none; background: transparent;")
    val.setObjectName("stat_value")
    layout.addWidget(val)

    # 副说明
    sub = QLabel(subtext)
    sub.setFont(QFont("Segoe UI", 9))
    sub.setStyleSheet("color: #a8b3c1; border: none; background: transparent;")
    sub.setObjectName("stat_subtext")
    layout.addWidget(sub)

    return card


class OverviewTab(QWidget):
    """概览仪表板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)

        # 1. 顶部统计卡片行 (5 核心指标)
        self._cards_layout = QHBoxLayout()
        self._cards_layout.setSpacing(14)

        self._card_cost = _stat_card("总花费金额", "$0.00", "累计 API 账单估算", "#c7a7ff")
        self._card_tokens = _stat_card("总 Token 消耗", "0", "全工具累计 Token", "#00bceb")
        self._card_avg_cost = _stat_card("平均会话花费", "$0.00", "单会话平均成本", "#66d990")
        self._card_sessions = _stat_card("总会话数", "0", "已记录开发会话", "#ffb457")
        self._card_execs = _stat_card("执行轮次", "0", "总交互响应次数", "#7fdbf2")

        self._cards_layout.addWidget(self._card_cost)
        self._cards_layout.addWidget(self._card_tokens)
        self._cards_layout.addWidget(self._card_avg_cost)
        self._cards_layout.addWidget(self._card_sessions)
        self._cards_layout.addWidget(self._card_execs)
        self._layout.addLayout(self._cards_layout)

        # 2. 图表区 (卡片式容器包裹)
        self._charts_layout = QHBoxLayout()
        self._charts_layout.setSpacing(16)

        # 饼图外框卡片
        self._pie_card = QFrame()
        self._pie_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        self._pie_card_layout = QVBoxLayout(self._pie_card)
        self._pie_card_layout.setContentsMargins(14, 12, 14, 12)
        self._pie_card_layout.setSpacing(8)

        lbl_pie_title = QLabel("模型 Token 消耗构成")
        lbl_pie_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_pie_title.setStyleSheet("color: #f6f8fb; border: none; background: transparent; padding: 4px 4px 2px 4px;")
        self._pie_card_layout.addWidget(lbl_pie_title)

        self._pie_widget = QLabel("正在分析模型构成...")
        self._pie_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pie_widget.setStyleSheet("color: #7d8ba0; font-size: 13px; border: none;")
        self._pie_widget.setMinimumHeight(380)
        self._pie_card_layout.addWidget(self._pie_widget)

        # 折线图外框卡片
        self._line_card = QFrame()
        self._line_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        self._line_card_layout = QVBoxLayout(self._line_card)
        self._line_card_layout.setContentsMargins(14, 12, 14, 12)
        self._line_card_layout.setSpacing(8)

        # 头部：标题与时间范围切换胶囊
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        lbl_trend_title = QLabel("每日 Token 消耗趋势")
        lbl_trend_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_trend_title.setStyleSheet("color: #f6f8fb; border: none; background: transparent;")
        header_layout.addWidget(lbl_trend_title)
        header_layout.addStretch()

        from PySide6.QtWidgets import QPushButton, QButtonGroup
        self._range_group = QButtonGroup(self)
        self._range_group.setExclusive(True)
        self._range_buttons = {}

        ranges = [("14天", 14), ("30天", 30), ("90天", 90), ("全部", 0)]
        self._selected_days_limit = 30

        btn_container = QFrame()
        btn_container.setStyleSheet("""
            QFrame {
                background: #182230;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 1px;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #7d8ba0;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                color: #f6f8fb;
                background: rgba(255, 255, 255, 0.06);
            }
            QPushButton:checked {
                color: #001f30;
                background: #00bceb;
            }
        """)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(2, 2, 2, 2)
        btn_layout.setSpacing(2)

        for label, limit in ranges:
            btn = QPushButton(label)
            btn.setCheckable(True)
            if limit == 30:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, l=limit: self._on_range_changed(l))
            self._range_group.addButton(btn)
            self._range_buttons[limit] = btn
            btn_layout.addWidget(btn)

        header_layout.addWidget(btn_container)
        self._line_card_layout.addLayout(header_layout)

        self._line_widget = QLabel("正在聚合每日趋势...")
        self._line_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._line_widget.setStyleSheet("color: #7d8ba0; font-size: 13px; border: none;")
        self._line_widget.setMinimumHeight(380)
        self._line_card_layout.addWidget(self._line_widget)

        self._charts_layout.addWidget(self._pie_card, stretch=2)
        self._charts_layout.addWidget(self._line_card, stretch=3)
        self._layout.addLayout(self._charts_layout)

    def _on_range_changed(self, limit: int):
        self._selected_days_limit = limit
        self._refresh_line_chart()

    def _update_card(self, card: QFrame, value: str, subtext: str = None):
        """更新卡片数值与副标"""
        val_label = card.findChild(QLabel, "stat_value")
        if val_label:
            val_label.setText(value)
        if subtext is not None:
            sub_label = card.findChild(QLabel, "stat_subtext")
            if sub_label:
                sub_label.setText(subtext)

    def update_data(self, data: dict):
        """接收完整数据 dict 并更新 UI"""
        cross = data.get("cross", {})

        # 更新统计卡片
        cost = float(cross.get("total_cost", 0))
        tokens = int(cross.get("total_tokens", 0))
        sessions = int(cross.get("total_sessions", 0))
        execs = int(cross.get("total_executions", 0))

        avg_cost = (cost / sessions) if sessions > 0 else 0.0
        avg_tokens = (tokens // sessions) if sessions > 0 else 0

        self._update_card(self._card_cost, f"${cost:.2f}", "全时段总支出")
        self._update_card(self._card_tokens, _format_tokens(tokens), f"均会话 {avg_tokens:,} Token")
        self._update_card(self._card_avg_cost, f"${avg_cost:.3f}" if avg_cost < 1 else f"${avg_cost:.2f}", "每单会话均价")
        self._update_card(self._card_sessions, f"{sessions:,}", "本地已发现会话")
        self._update_card(self._card_execs, f"{execs:,}", "调用/交互请求数")

        # 更新饼图：按 Token 占比
        model_mix = cross.get("model_mix") or []
        if model_mix:
            pie = create_pie_chart(model_mix, "", "tokens")
            self._pie_card_layout.replaceWidget(self._pie_widget, pie)
            self._pie_widget.deleteLater()
            self._pie_widget = pie

        # 过滤与聚合 sessions 每日趋势数据（严格过滤非法日期与?）
        import datetime
        logs = data.get("logs", {}) or {}
        all_sessions = logs.get("sessions") or []
        daily_map = {}
        for s in all_sessions:
            start_val = s.get("start") or s.get("started") or s.get("mtime") or 0
            day = None
            if isinstance(start_val, (int, float)) and start_val > 0:
                try:
                    day = datetime.datetime.fromtimestamp(start_val).strftime("%Y-%m-%d")
                except Exception:
                    day = None
            elif isinstance(start_val, str) and len(start_val) >= 10:
                candidate = start_val[:10]
                # 严格校验 YYYY-MM-DD 格式
                parts = candidate.split("-")
                if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
                    day = candidate

            if not day:
                continue

            t = int(s.get("tokens") or 0)
            daily_map[day] = daily_map.get(day, 0) + t

        self._full_daily = [{"day": k, "tokens": v} for k, v in sorted(daily_map.items())]
        self._refresh_line_chart()

    def _refresh_line_chart(self):
        """根据当前选中的时间范围刷新折线图"""
        if not hasattr(self, "_full_daily") or not self._full_daily:
            return

        # 获取时间范围过滤
        days_limit = getattr(self, "_selected_days_limit", 30)
        if days_limit and days_limit > 0 and len(self._full_daily) > days_limit:
            chart_data = self._full_daily[-days_limit:]
        else:
            chart_data = self._full_daily

        line = create_line_chart(chart_data, "day", "tokens", "", "Token")
        self._line_card_layout.replaceWidget(self._line_widget, line)
        self._line_widget.deleteLater()
        self._line_widget = line

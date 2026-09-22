# -*- coding: utf-8 -*-
"""每日花费与月度趋势标签页

展示每日花费/Token柱状图，以及历史月份汇总明细表格。
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QHeaderView,
    QAbstractItemView, QSplitter, QFrame, QPushButton, QButtonGroup,
)

from desktop.widgets.charts import create_bar_chart, _fmt_tokens


class NumericSortProxy(QSortFilterProxyModel):
    """支持数值正确排序的代理模型"""

    def lessThan(self, left, right):
        left_val = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
        right_val = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)
        if left_val is not None and right_val is not None:
            try:
                return float(left_val) < float(right_val)
            except (ValueError, TypeError):
                pass
        return super().lessThan(left, right)


class DailyTab(QWidget):
    """每日花费与月度汇总标签页"""

    MONTHLY_HEADERS = ["时间跨度", "总花费", "总 Token 数", "会话总数"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_chart_view = None
        self._full_daily = []
        self._full_monthly = []
        self._selected_range_limit = 30

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 每日花费柱状图卡片容器
        self.chart_card = QFrame()
        self.chart_card.setMinimumHeight(320)
        self.chart_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        self.chart_layout = QVBoxLayout(self.chart_card)
        self.chart_layout.setContentsMargins(14, 12, 14, 12)
        self.chart_layout.setSpacing(6)

        # 头部：标题与时间范围切换胶囊
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        self.lbl_trend_title = QLabel("Token 消耗趋势")
        self.lbl_trend_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_trend_title.setStyleSheet("color: #f6f8fb; border: none; background: transparent;")
        header_layout.addWidget(self.lbl_trend_title)
        header_layout.addStretch()

        self._range_group = QButtonGroup(self)
        self._range_group.setExclusive(True)
        ranges = [("14天", 14), ("30天", 30), ("90天", 90), ("全部", 0)]

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
            btn_layout.addWidget(btn)

        header_layout.addWidget(btn_container)
        self.chart_layout.addLayout(header_layout)

        self.lbl_chart_empty = QLabel("暂无趋势图表数据")
        self.lbl_chart_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_empty.setStyleSheet("color: #7d8ba0; border: none;")
        self.chart_layout.addWidget(self.lbl_chart_empty)
        splitter.addWidget(self.chart_card)

        # 2. 月度汇总表格卡片容器
        self.table_card = QFrame()
        self.table_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(8)

        lbl_monthly_title = QLabel("周期汇总明细（年度 / 月度）")
        lbl_monthly_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f6f8fb;")
        table_layout.addWidget(lbl_monthly_title)

        self.source_model = QStandardItemModel()
        self.source_model.setHorizontalHeaderLabels(self.MONTHLY_HEADERS)

        self.proxy_model = NumericSortProxy(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        table_layout.addWidget(self.table)
        splitter.addWidget(self.table_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 240])
        layout.addWidget(splitter)

    def _on_range_changed(self, limit: int):
        self._selected_range_limit = limit
        self._refresh_chart()

    def _refresh_chart(self):
        """根据当前选中的时间范围智能渲染柱状图，杜绝滚动条，清晰呈现X轴刻度尺"""
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

        if not self._full_daily and not self._full_monthly:
            self.lbl_chart_empty.show()
            return

        self.lbl_chart_empty.hide()
        limit = self._selected_range_limit

        if limit == 14:
            chart_data = self._full_daily[-14:] if len(self._full_daily) > 14 else self._full_daily
            title = "最近 14 天每日 Token 消耗"
            x_k = "day"
        elif limit == 30:
            chart_data = self._full_daily[-30:] if len(self._full_daily) > 30 else self._full_daily
            title = "最近 30 天每日 Token 消耗"
            x_k = "day"
        elif limit == 90:
            raw_90 = self._full_daily[-90:] if len(self._full_daily) > 90 else self._full_daily
            if len(raw_90) > 35:
                # 按周（每 7 天）聚合，保持约 12~13 根饱满柱子
                chart_data = []
                for chunk_idx in range(0, len(raw_90), 7):
                    chunk = raw_90[chunk_idx:chunk_idx + 7]
                    chunk_tokens = sum(d["tokens"] for d in chunk)
                    first_day = chunk[0]["day"]
                    label = first_day[5:] + "周"
                    chart_data.append({"day": label, "tokens": chunk_tokens})
                title = "最近 90 天周度 Token 趋势"
            else:
                chart_data = raw_90
                title = "最近 90 天每日 Token 消耗"
            x_k = "day"
        else:  # 全部：按月展示历史柱状图对比
            chart_data = [{"month": m["month"], "tokens": m["tokens"]} for m in self._full_monthly]
            title = "历史各月 Token 消耗对比"
            x_k = "month"

        chart_view = create_bar_chart(
            chart_data, x_key=x_k, y_key="tokens",
            title=title, y_label="Token", color="#00bceb"
        )
        chart_view.setMinimumHeight(280)
        self._current_chart_view = chart_view
        self.chart_layout.addWidget(chart_view)

    def update_data(self, data: dict):
        """接收数据并刷新每日图表与月度/年度表格"""
        cross = data.get("cross", {})
        logs = data.get("logs", {}) or {}
        all_sessions = logs.get("sessions") or []

        daily_map = {}
        monthly_map = {}
        yearly_map = {}
        import datetime
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
                parts = candidate.split("-")
                if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
                    day = candidate

            if not day:
                continue

            month = day[:7]
            year = day[:4]
            t = int(s.get("tokens") or 0)
            c = float(s.get("cost") or 0.0)
            daily_map[day] = daily_map.get(day, 0) + t
            monthly_map[month] = {
                "tokens": monthly_map.get(month, {}).get("tokens", 0) + t,
                "cost": monthly_map.get(month, {}).get("cost", 0.0) + c,
                "sessions": monthly_map.get(month, {}).get("sessions", 0) + 1,
            }
            yearly_map[year] = {
                "tokens": yearly_map.get(year, {}).get("tokens", 0) + t,
                "cost": yearly_map.get(year, {}).get("cost", 0.0) + c,
                "sessions": yearly_map.get(year, {}).get("sessions", 0) + 1,
            }

        self._full_daily = [{"day": k, "tokens": v} for k, v in sorted(daily_map.items())]
        self._full_monthly = [{"month": k, **v} for k, v in sorted(monthly_map.items())]
        monthly = self._full_monthly
        yearly = [{"year": k, **v} for k, v in sorted(yearly_map.items())]

        # 刷新柱状图
        self._refresh_chart()

        # 刷新月度+年度表格
        self.source_model.removeRows(0, self.source_model.rowCount())
        # 年度行（加粗突出）
        for y in yearly:
            item_year = QStandardItem(f"▎ {y['year']} 年度汇总")
            item_year.setData(y["cost"], Qt.ItemDataRole.UserRole)
            item_cost = QStandardItem(f"${y['cost']:.2f}")
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_cost.setData(y["cost"], Qt.ItemDataRole.UserRole)
            item_cost.setForeground(QColor("#c7a7ff"))

            item_tokens = QStandardItem(_fmt_tokens(y["tokens"]))
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(y["tokens"], Qt.ItemDataRole.UserRole)
            item_tokens.setForeground(QColor("#00bceb"))

            item_sessions = QStandardItem(f"{y['sessions']:,}")
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_sessions.setData(y["sessions"], Qt.ItemDataRole.UserRole)

            for it in (item_year, item_cost, item_tokens, item_sessions):
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            self.source_model.appendRow([item_year, item_cost, item_tokens, item_sessions])

        # 月度行
        for m in monthly:
            item_month = QStandardItem(f"   {m['month']}")
            item_cost = QStandardItem(f"${m['cost']:.2f}")
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_cost.setData(m["cost"], Qt.ItemDataRole.UserRole)
            if m['cost'] > 0:
                item_cost.setForeground(QColor("#c7a7ff"))

            item_tokens = QStandardItem(_fmt_tokens(m["tokens"]))
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(m["tokens"], Qt.ItemDataRole.UserRole)

            item_sessions = QStandardItem(f"{m['sessions']:,}")
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_sessions.setData(m["sessions"], Qt.ItemDataRole.UserRole)
            self.source_model.appendRow([item_month, item_cost, item_tokens, item_sessions])

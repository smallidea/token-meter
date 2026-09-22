# -*- coding: utf-8 -*-
"""每日花费与月度趋势标签页

展示每日花费/Token柱状图，以及历史月份汇总明细表格。
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QHeaderView,
    QAbstractItemView, QSplitter, QScrollArea, QFrame,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 每日花费柱状图卡片容器
        self.chart_card = QFrame()
        self.chart_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        self.chart_layout = QVBoxLayout(self.chart_card)
        self.chart_layout.setContentsMargins(12, 12, 12, 12)

        self.lbl_chart_empty = QLabel("暂无每日花费图表数据")
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
        layout.addWidget(splitter)

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

        daily = [{"day": k, "tokens": v} for k, v in sorted(daily_map.items())]
        monthly = [{"month": k, **v} for k, v in sorted(monthly_map.items())]
        yearly = [{"year": k, **v} for k, v in sorted(yearly_map.items())]

        # 刷新每日柱状图
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

        if daily:
            self.lbl_chart_empty.hide()
            chart_view = create_bar_chart(
                daily, x_key="day", y_key="tokens",
                title="每日 Token 消耗趋势", y_label="Token", color="#00bceb"
            )
            n = len(daily)
            if n > 40:
                chart_view.setMinimumWidth(n * 12)
                scroll = QScrollArea()
                scroll.setWidget(chart_view)
                scroll.setWidgetResizable(True)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self._current_chart_view = scroll
                self.chart_layout.addWidget(scroll)
            else:
                self._current_chart_view = chart_view
                self.chart_layout.addWidget(chart_view)
        else:
            self.lbl_chart_empty.show()

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

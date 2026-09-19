# -*- coding: utf-8 -*-
"""每日花费与月度趋势标签页

展示过去 30 天每日花费柱状图，以及历史月份汇总明细表格。
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableView, QHeaderView,
    QAbstractItemView, QSplitter,
)

from desktop.widgets.charts import create_bar_chart


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

    MONTHLY_HEADERS = ["月份", "总花费", "总 Token 数", "会话总数"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_chart_view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 每日花费柱状图容器
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_chart_empty = QLabel("暂无每日花费图表数据")
        self.lbl_chart_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_empty.setStyleSheet("color: #7d8ba0;")
        self.chart_layout.addWidget(self.lbl_chart_empty)
        splitter.addWidget(self.chart_container)

        # 2. 月度汇总表格容器
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        lbl_monthly_title = QLabel("月度汇总明细")
        lbl_monthly_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #f6f8fb; margin-bottom: 4px;")
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

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def update_data(self, data: dict):
        """接收数据并刷新每日图表与月度表格"""
        cross = data.get("cross", {})
        daily = cross.get("daily") or []
        monthly = cross.get("monthly") or []

        # 刷新每日柱状图
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

        if daily:
            self.lbl_chart_empty.hide()
            # 默认 daily 按最近日期排，反转成按时间先后从左到右显示
            reversed_daily = list(reversed(daily[:30]))
            chart_view = create_bar_chart(
                reversed_daily, x_key="day", y_key="cost",
                title="最近 30 天每日花费", y_label="花费 ($)", color="#00bceb"
            )
            self._current_chart_view = chart_view
            self.chart_layout.addWidget(chart_view)
        else:
            self.lbl_chart_empty.show()

        # 刷新月度表格
        self.source_model.removeRows(0, self.source_model.rowCount())
        for m in monthly:
            month_str = str(m.get("month") or "未知")
            cost = float(m.get("cost") or 0.0)
            tokens = int(m.get("tokens") or 0)
            sessions = int(m.get("sessions") or 0)

            item_month = QStandardItem(month_str)

            item_cost = QStandardItem(f"${cost:.2f}")
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_cost.setData(cost, Qt.ItemDataRole.UserRole)

            item_tokens = QStandardItem(f"{tokens:,}")
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(tokens, Qt.ItemDataRole.UserRole)

            item_sessions = QStandardItem(str(sessions))
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_sessions.setData(sessions, Qt.ItemDataRole.UserRole)

            self.source_model.appendRow([item_month, item_cost, item_tokens, item_sessions])

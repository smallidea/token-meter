# -*- coding: utf-8 -*-
"""工具（runtime）统计标签页

展示各个工具/运行时（Claude/Codex/Cursor/OpenCode/Kiro/Antigravity/
WorkBuddy/Trae CN）的会话数、Token 消耗与占比。
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QHeaderView,
    QAbstractItemView, QSplitter, QFrame,
)

from desktop.widgets.charts import create_bar_chart, _fmt_tokens


# provider 后端 id -> 中文/展示名
PROVIDER_LABELS = {
    "claude": "Claude",
    "codex": "Codex",
    "cursor": "Cursor (本地估算)",
    "opencode": "OpenCode",
    "kiro": "Kiro",
    "antigravity": "Antigravity",
    "workbuddy": "WorkBuddy",
    "traecn": "Trae CN",
    "trae_cn": "Trae CN",
    "hermes": "Hermes",
}


def provider_label(pid: str) -> str:
    pid = str(pid or "").strip()
    if pid in PROVIDER_LABELS:
        return PROVIDER_LABELS[pid]
    return pid[:1].upper() + pid[1:] if pid else "未知"


class NumericSortProxy(QSortFilterProxyModel):
    """支持 UserRole 数值排序的代理模型"""

    def lessThan(self, left, right):
        left_val = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
        right_val = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)
        if left_val is not None and right_val is not None:
            try:
                return float(left_val) < float(right_val)
            except (ValueError, TypeError):
                pass
        return super().lessThan(left, right)


class ToolsTab(QWidget):
    """工具（runtime）花费统计标签页"""

    HEADERS = ["AI 辅助工具", "会话总数", "Token 消耗", "Token 占比"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_chart_view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 顶部指标栏
        top_bar = QHBoxLayout()
        self.lbl_tools_count = QLabel("已接入工具: 0 款")
        self.lbl_tools_count.setStyleSheet("""
            QLabel {
                background: #17212b;
                color: #00bceb;
                border: 1px solid rgba(0, 188, 235, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11.5px;
            }
        """)
        top_bar.addWidget(self.lbl_tools_count)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 图表卡片
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

        self.lbl_empty = QLabel("暂无工具数据")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #7d8ba0; border: none;")
        self.chart_layout.addWidget(self.lbl_empty)
        splitter.addWidget(self.chart_card)

        # 2. 表格卡片
        self.table_card = QFrame()
        self.table_card.setStyleSheet("""
            QFrame {
                background: #111820;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)

        self.source_model = QStandardItemModel()
        self.source_model.setHorizontalHeaderLabels(self.HEADERS)

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
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter)

    def _clear_chart(self):
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

    def update_data(self, data: dict):
        """接收数据并刷新（以 Token 消耗为主指标）"""
        cross = (data or {}).get("cross", {}) or {}
        providers = cross.get("providers") or []
        providers = [p for p in providers if isinstance(p, dict)]

        # 从 model_stats/models/model_mix 按 runtime 聚合
        ms = cross.get("model_stats") or {}
        if isinstance(ms, dict):
            models = ms.get("models") or []
        elif isinstance(ms, list):
            models = ms
        else:
            models = []
        if not models:
            models = cross.get("model_mix") or []
        runtime_tokens = {}
        total_tokens = 0
        for m in models:
            if not isinstance(m, dict):
                continue
            rt = str(m.get("runtime") or "").lower()
            t = m.get("tokens")
            tok = int(t) if t else (int(m.get("input_tokens") or 0) + int(m.get("output_tokens") or 0))
            runtime_tokens[rt] = runtime_tokens.get(rt, 0) + tok
            total_tokens += tok

        for p in providers:
            pid = str(p.get("provider") or "unknown").lower()
            p["_tokens"] = runtime_tokens.get(pid, 0)
        providers.sort(key=lambda p: p.get("_tokens", 0), reverse=True)

        self.lbl_tools_count.setText(f"已接入工具: {len(providers)} 款")

        # 重建表格
        self.source_model.removeRows(0, self.source_model.rowCount())
        for p in providers:
            pid = str(p.get("provider") or "未知")
            label = provider_label(pid)
            tokens = int(p.get("_tokens") or 0)
            sessions = int(p.get("sessions") or 0)
            share_pct = (tokens / total_tokens * 100.0) if total_tokens > 0 else 0.0

            item_name = QStandardItem(label)
            item_name.setToolTip(f"内部代号: {pid}")

            item_sessions = QStandardItem(f"{sessions:,}")
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_sessions.setData(sessions, Qt.ItemDataRole.UserRole)

            item_tokens = QStandardItem(_fmt_tokens(tokens))
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(tokens, Qt.ItemDataRole.UserRole)

            item_share = QStandardItem(f"{share_pct:.1f}%")
            item_share.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_share.setData(share_pct, Qt.ItemDataRole.UserRole)

            self.source_model.appendRow([item_name, item_sessions, item_tokens, item_share])

        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)

        # 重建柱状图
        self._clear_chart()
        if providers:
            self.lbl_empty.hide()
            chart_data = [
                {"provider": provider_label(p.get("provider")),
                 "tokens": int(p.get("_tokens") or 0)}
                for p in providers
            ]
            chart_view = create_bar_chart(
                chart_data, x_key="provider", y_key="tokens",
                title="各工具 Token 消耗分布", y_label="Token", color="#00bceb"
            )
            self._current_chart_view = chart_view
            self.chart_layout.addWidget(chart_view)
        else:
            self.lbl_empty.show()

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
        logs = (data or {}).get("logs", {}) or {}
        all_sessions = logs.get("sessions") or []

        def _norm(s: str) -> str:
            return str(s or "").lower().replace(" ", "").replace("-", "").replace("_", "")

        # 1. 优先从全量 sessions 聚合各工具真实会话数与 Token
        tool_stats = {}
        for s in all_sessions:
            if not isinstance(s, dict):
                continue
            p_raw = str(s.get("runtime") or s.get("provider") or s.get("client") or "other").strip()
            key = _norm(p_raw)
            tok = int(s.get("tokens") or 0)
            c = float(s.get("cost") or 0.0)
            if key not in tool_stats:
                tool_stats[key] = {
                    "provider": p_raw,
                    "label": provider_label(p_raw),
                    "sessions": 0,
                    "tokens": 0,
                    "cost": 0.0,
                }
            tool_stats[key]["sessions"] += 1
            tool_stats[key]["tokens"] += tok
            tool_stats[key]["cost"] += c

        # 2. 结合 cross.get("providers") 补充或校准
        providers = cross.get("providers") or []
        for p in providers:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("provider") or "unknown")
            key = _norm(pid)
            if key in tool_stats:
                tool_stats[key]["label"] = provider_label(pid)
                if tool_stats[key]["sessions"] == 0:
                    tool_stats[key]["sessions"] = int(p.get("sessions") or 0)
            else:
                tool_stats[key] = {
                    "provider": pid,
                    "label": provider_label(pid),
                    "sessions": int(p.get("sessions") or 0),
                    "tokens": 0,
                    "cost": float(p.get("cost") or 0.0),
                }

        # 3. 补充从 model_mix / model_stats 计算的 token（双重保障）
        ms = cross.get("model_stats") or {}
        models = (ms.get("models") if isinstance(ms, dict) else ms) or cross.get("model_mix") or []
        for m in models:
            if not isinstance(m, dict):
                continue
            rt_key = _norm(m.get("runtime") or "")
            t = m.get("tokens")
            tok = int(t) if t else (int(m.get("input_tokens") or 0) + int(m.get("output_tokens") or 0))
            if rt_key in tool_stats and tool_stats[rt_key]["tokens"] == 0:
                tool_stats[rt_key]["tokens"] += tok

        tool_list = list(tool_stats.values())
        total_tokens = sum(t["tokens"] for t in tool_list) or 1
        tool_list.sort(key=lambda x: x["tokens"], reverse=True)

        self.lbl_tools_count.setText(f"已接入工具: {len(tool_list)} 款")

        # 重建表格
        self.source_model.removeRows(0, self.source_model.rowCount())
        for item in tool_list:
            label = item["label"]
            pid = item["provider"]
            tokens = int(item["tokens"])
            sessions = int(item["sessions"])
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
        if tool_list:
            self.lbl_empty.hide()
            chart_data = [
                {"provider": t["label"], "tokens": int(t["tokens"])}
                for t in tool_list
            ]
            chart_view = create_bar_chart(
                chart_data, x_key="provider", y_key="tokens",
                title="各工具 Token 消耗分布", y_label="Token", color="#00bceb"
            )
            self._current_chart_view = chart_view
            self.chart_layout.addWidget(chart_view)
        else:
            self.lbl_empty.show()

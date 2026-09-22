import datetime
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QHeaderView,
    QAbstractItemView, QSplitter, QFrame, QComboBox,
)

from desktop.widgets.charts import create_bar_chart, _fmt_tokens, _fmt_money


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
    "grokbot": "Grok Bot",
    "grok_bot": "Grok Bot",
    "grok": "Grok Bot",
    "doubao": "豆包 (Doubao)",
    "doubao_agent": "豆包 (Doubao)",
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
    """工具（runtime）月度与累计花费/Token 统计标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_chart_view = None
        self._cached_tool_stats = {}
        self._cached_all_months = []
        self._is_updating_combo = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 顶部指标栏与月份选择器
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

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

        self.lbl_month_hint = QLabel("统计范围:")
        self.lbl_month_hint.setStyleSheet("color: #7d8ba0; font-size: 12px; margin-left: 8px;")
        top_bar.addWidget(self.lbl_month_hint)

        self.combo_month = QComboBox()
        self.combo_month.setMinimumWidth(160)
        self.combo_month.setStyleSheet("""
            QComboBox {
                background: #17212b;
                color: #f6f8fb;
                border: 1px solid rgba(0, 188, 235, 0.35);
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QComboBox:hover {
                border-color: #00bceb;
            }
            QComboBox QAbstractItemView {
                background: #17212b;
                color: #f6f8fb;
                selection-background-color: rgba(0, 188, 235, 0.3);
                border: 1px solid rgba(0, 188, 235, 0.3);
                border-radius: 6px;
                padding: 4px;
            }
        """)
        self.combo_month.addItem("全部月份 (历史累计)")
        self.combo_month.currentIndexChanged.connect(self._on_month_selection_changed)
        top_bar.addWidget(self.combo_month)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 图表卡片
        self.chart_card = QFrame()
        self.chart_card.setMinimumHeight(300)
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
        self.proxy_model = NumericSortProxy(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        table_layout.addWidget(self.table)
        splitter.addWidget(self.table_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([360, 260])
        layout.addWidget(splitter)

    def _clear_chart(self):
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

    def _on_month_selection_changed(self, idx: int):
        if self._is_updating_combo:
            return
        self._render_view()

    def update_data(self, data: dict):
        """接收全量数据，按工具与月份进行双重透视聚合"""
        cross = (data or {}).get("cross", {}) or {}
        logs = (data or {}).get("logs", {}) or {}
        all_sessions = logs.get("sessions") or []

        def _norm(s: str) -> str:
            return str(s or "").lower().replace(" ", "").replace("-", "").replace("_", "")

        tool_stats = {}
        all_months_set = set()

        for s in all_sessions:
            if not isinstance(s, dict):
                continue
            p_raw = str(s.get("runtime") or s.get("provider") or s.get("client") or "other").strip()
            key = _norm(p_raw)
            tok = int(s.get("tokens") or 0)
            c = float(s.get("cost") or 0.0)

            # 解析月份
            mtime = s.get("mtime") or s.get("last_ts") or s.get("ts") or 0
            month = "未知"
            if mtime:
                try:
                    month = datetime.datetime.fromtimestamp(float(mtime)).strftime("%Y-%m")
                    all_months_set.add(month)
                except Exception:
                    month = "未知"

            if key not in tool_stats:
                tool_stats[key] = {
                    "provider": p_raw,
                    "label": provider_label(p_raw),
                    "total_sessions": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "months": {},
                }
            tool_stats[key]["total_sessions"] += 1
            tool_stats[key]["total_tokens"] += tok
            tool_stats[key]["total_cost"] += c

            if month not in tool_stats[key]["months"]:
                tool_stats[key]["months"][month] = {"tokens": 0, "sessions": 0, "cost": 0.0}
            tool_stats[key]["months"][month]["tokens"] += tok
            tool_stats[key]["months"][month]["sessions"] += 1
            tool_stats[key]["months"][month]["cost"] += c

        # 结合 cross.get("providers") 补充
        for p in cross.get("providers") or []:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("provider") or "unknown")
            key = _norm(pid)
            if key in tool_stats:
                tool_stats[key]["label"] = provider_label(pid)
                if tool_stats[key]["total_sessions"] == 0:
                    tool_stats[key]["total_sessions"] = int(p.get("sessions") or 0)
            else:
                tool_stats[key] = {
                    "provider": pid,
                    "label": provider_label(pid),
                    "total_sessions": int(p.get("sessions") or 0),
                    "total_tokens": 0,
                    "total_cost": float(p.get("cost") or 0.0),
                    "months": {},
                }

        self._cached_tool_stats = tool_stats
        self._cached_all_months = sorted(list(all_months_set), reverse=True)

        self.lbl_tools_count.setText(f"已接入工具: {len(tool_stats)} 款")

        # 更新月份下拉框
        curr_selected = self.combo_month.currentText()
        self._is_updating_combo = True
        self.combo_month.clear()
        self.combo_month.addItem("全部月份 (历史累计)")
        for m in self._cached_all_months:
            self.combo_month.addItem(m)

        # 尝试恢复之前的选择
        idx = self.combo_month.findText(curr_selected)
        if idx >= 0:
            self.combo_month.setCurrentIndex(idx)
        else:
            self.combo_month.setCurrentIndex(0)
        self._is_updating_combo = False

        self._render_view()

    def _render_view(self):
        """根据当前选中的月份重新渲染表格与柱状图"""
        tool_stats = self._cached_tool_stats
        all_months = self._cached_all_months
        selected_text = self.combo_month.currentText()
        is_all_months = selected_text.startswith("全部月份") or not selected_text

        cur_month = all_months[0] if len(all_months) > 0 else "当月"
        prev_month = all_months[1] if len(all_months) > 1 else "上月"

        selected_month = None if is_all_months else selected_text

        # 准备行数据
        rows = []
        total_scope_tokens = 0

        for key, info in tool_stats.items():
            label = info["label"]
            pid = info["provider"]
            m_dict = info["months"]

            if is_all_months:
                tok_total = info["total_tokens"]
                tok_cur = m_dict.get(cur_month, {}).get("tokens", 0)
                tok_prev = m_dict.get(prev_month, {}).get("tokens", 0)
                sessions = info["total_sessions"]
                cost = info["total_cost"]
                total_scope_tokens += tok_total
                rows.append({
                    "label": label,
                    "provider": pid,
                    "tok_cur": tok_cur,
                    "tok_prev": tok_prev,
                    "tok_main": tok_total,
                    "sessions": sessions,
                    "cost": cost,
                })
            else:
                month_data = m_dict.get(selected_month, {"tokens": 0, "sessions": 0, "cost": 0.0})
                tok_month = month_data["tokens"]
                sessions_month = month_data["sessions"]
                cost_month = month_data["cost"]
                total_scope_tokens += tok_month
                rows.append({
                    "label": label,
                    "provider": pid,
                    "tok_main": tok_month,
                    "sessions": sessions_month,
                    "cost": cost_month,
                })

        # 按当前主指标 Token 降序排列
        rows.sort(key=lambda x: x["tok_main"], reverse=True)
        total_scope_tokens = max(1, total_scope_tokens)

        # 重建表格 Header 与内容
        self.source_model.clear()
        if is_all_months:
            headers = [
                "AI 辅助工具",
                f"当月 Token ({cur_month[-2:]}月)",
                f"上月 Token ({prev_month[-2:]}月)",
                "累计 Token 消耗",
                "总会话数",
                "累计占比",
            ]
            self.source_model.setHorizontalHeaderLabels(headers)
            for r in rows:
                item_name = QStandardItem(r["label"])
                item_name.setToolTip(f"内部标识: {r['provider']}")

                item_cur = QStandardItem(_fmt_tokens(r["tok_cur"]))
                item_cur.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_cur.setData(r["tok_cur"], Qt.ItemDataRole.UserRole)

                item_prev = QStandardItem(_fmt_tokens(r["tok_prev"]))
                item_prev.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_prev.setData(r["tok_prev"], Qt.ItemDataRole.UserRole)

                item_main = QStandardItem(_fmt_tokens(r["tok_main"]))
                item_main.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_main.setData(r["tok_main"], Qt.ItemDataRole.UserRole)

                item_sessions = QStandardItem(f"{r['sessions']:,}")
                item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_sessions.setData(r["sessions"], Qt.ItemDataRole.UserRole)

                pct = (r["tok_main"] / total_scope_tokens * 100.0)
                item_share = QStandardItem(f"{pct:.1f}%")
                item_share.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_share.setData(pct, Qt.ItemDataRole.UserRole)

                self.source_model.appendRow([item_name, item_cur, item_prev, item_main, item_sessions, item_share])

            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)

        else:
            headers = [
                "AI 辅助工具",
                f"{selected_month} Token 消耗",
                "当月会话数",
                "当月预估花费",
                "当月占比",
            ]
            self.source_model.setHorizontalHeaderLabels(headers)
            for r in rows:
                item_name = QStandardItem(r["label"])
                item_name.setToolTip(f"内部标识: {r['provider']}")

                item_main = QStandardItem(_fmt_tokens(r["tok_main"]))
                item_main.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_main.setData(r["tok_main"], Qt.ItemDataRole.UserRole)

                item_sessions = QStandardItem(f"{r['sessions']:,}")
                item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_sessions.setData(r["sessions"], Qt.ItemDataRole.UserRole)

                item_cost = QStandardItem(_fmt_money(r["cost"]))
                item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_cost.setData(r["cost"], Qt.ItemDataRole.UserRole)

                pct = (r["tok_main"] / total_scope_tokens * 100.0) if r["tok_main"] > 0 else 0.0
                item_share = QStandardItem(f"{pct:.1f}%")
                item_share.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_share.setData(pct, Qt.ItemDataRole.UserRole)

                self.source_model.appendRow([item_name, item_main, item_sessions, item_cost, item_share])

            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        # 重建柱状图
        self._clear_chart()
        chart_data = [
            {"provider": r["label"], "tokens": int(r["tok_main"])}
            for r in rows if r["tok_main"] > 0
        ]
        if chart_data:
            self.lbl_empty.hide()
            title = f"各工具 Token 消耗分布 ({selected_month})" if selected_month else "各工具 Token 消耗分布 (历史累计)"
            chart_view = create_bar_chart(
                chart_data, x_key="provider", y_key="tokens",
                title=title, y_label="Token", color="#00bceb"
            )
            chart_view.setMinimumHeight(260)
            self._current_chart_view = chart_view
            self.chart_layout.addWidget(chart_view)
        else:
            self.lbl_empty.setText(f"{selected_month} 暂无工具调用记录" if selected_month else "暂无工具数据")
            self.lbl_empty.show()


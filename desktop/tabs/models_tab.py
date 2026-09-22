# -*- coding: utf-8 -*-
"""模型统计标签页

展示各 AI 模型的调用频次、Token 消耗及花费统计，支持按项目筛选与柱状图可视化。
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableView, QHeaderView, QAbstractItemView, QSplitter, QFrame,
)

from desktop.widgets.charts import create_bar_chart, _fmt_tokens


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


class ModelsTab(QWidget):
    """模型统计标签页"""

    HEADERS = ["模型名称", "调用会话数", "Token 数", "花费金额", "花费占比"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_data = {}
        self._current_chart_view = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        lbl_proj = QLabel("项目筛选:")
        lbl_proj.setStyleSheet("color: #a8b3c1; font-weight: 600;")
        toolbar.addWidget(lbl_proj)

        self.combo_project = QComboBox()
        self.combo_project.addItem("所有项目")
        self.combo_project.currentTextChanged.connect(self._on_project_changed)
        toolbar.addWidget(self.combo_project)

        toolbar.addStretch()

        # 顶部指标小胶囊
        self.lbl_model_badge = QLabel("模型总数: 0")
        self.lbl_model_badge.setStyleSheet("""
            QLabel {
                background: #17212b;
                color: #c7a7ff;
                border: 1px solid rgba(199, 167, 255, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11.5px;
            }
        """)
        toolbar.addWidget(self.lbl_model_badge)

        layout.addLayout(toolbar)

        # 分割容器（上：图表卡片，下：明细表格卡片）
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. 图表卡片容器
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

        self.lbl_chart_empty = QLabel("暂无模型统计图表数据")
        self.lbl_chart_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_empty.setStyleSheet("color: #7d8ba0; border: none;")
        self.chart_layout.addWidget(self.lbl_chart_empty)
        splitter.addWidget(self.chart_card)

        # 2. 表格卡片容器
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

        # 表格选中/悬停联动柱状图高亮
        self.table.selectionModel().selectionChanged.connect(self._on_table_selection)
        self.table.entered.connect(self._on_table_entered)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        table_layout.addWidget(self.table)
        splitter.addWidget(self.table_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter)

    def _on_project_changed(self, project_name: str):
        """项目筛选切换"""
        if not self._raw_data:
            return

        from token_meter import app

        if not project_name or project_name == "所有项目":
            cross = self._raw_data.get("cross", {})
            raw_stats = cross.get("model_stats")
            if isinstance(raw_stats, dict):
                model_stats = raw_stats.get("models") or []
            elif isinstance(raw_stats, list):
                model_stats = raw_stats
            else:
                model_stats = cross.get("model_mix") or []
            total_cost = float(cross.get("total_cost") or 0.0)
            self._render_models(model_stats, total_cost)
        else:
            try:
                payload, status = app.project_model_stats(project_name)
                if status == 200 and isinstance(payload, dict):
                    models = payload.get("models") or []
                    total_cost = sum(float(m.get("cost") or 0.0) for m in models if isinstance(m, dict))
                    self._render_models(models, total_cost)
                else:
                    self._render_models([], 0.0)
            except Exception:
                self._render_models([], 0.0)

    def _render_models(self, models: list, total_cost: float):
        """渲染图表与表格"""
        self.source_model.removeRows(0, self.source_model.rowCount())

        # 清除旧图表
        if self._current_chart_view:
            self.chart_layout.removeWidget(self._current_chart_view)
            self._current_chart_view.deleteLater()
            self._current_chart_view = None

        if not models:
            self.lbl_chart_empty.show()
            self.lbl_model_badge.setText("模型总数: 0")
            return

        self.lbl_chart_empty.hide()

        chart_data = []
        valid_models = [m for m in models if isinstance(m, dict)]
        self.lbl_model_badge.setText(f"活跃模型: {len(valid_models)} 个")

        def _tok(m):
            t = m.get("tokens")
            if t:
                return float(t)
            return float(int(m.get("input_tokens") or 0) + int(m.get("output_tokens") or 0))

        for m in sorted(valid_models, key=_tok, reverse=True):
            model_name = str(m.get("model") or "未知")
            cost = float(m.get("cost") or 0.0)
            tokens = int(_tok(m))
            sessions = int(m.get("sessions") or m.get("logs") or m.get("requests") or m.get("executions") or 0)
            share_pct = (cost / total_cost * 100.0) if total_cost > 0 else 0.0

            chart_data.append({"model": model_name, "tokens": tokens})

            item_name = QStandardItem(model_name)
            runtime = str(m.get("runtime") or "")
            if runtime:
                item_name.setToolTip(f"运行时: {runtime}")

            item_sessions = QStandardItem(f"{sessions:,}")
            item_sessions.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_sessions.setData(sessions, Qt.ItemDataRole.UserRole)

            item_tokens = QStandardItem(_fmt_tokens(tokens))
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(tokens, Qt.ItemDataRole.UserRole)

            cost_str = f"${cost:.4f}" if 0 < cost < 0.01 else f"${cost:.2f}"
            item_cost = QStandardItem(cost_str)
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_cost.setData(cost, Qt.ItemDataRole.UserRole)

            item_share = QStandardItem(f"{share_pct:.1f}%")
            item_share.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_share.setData(share_pct, Qt.ItemDataRole.UserRole)

            self.source_model.appendRow([
                item_name, item_sessions, item_tokens, item_cost, item_share
            ])

        # 创建并展示柱状图（按 Token 消耗排名）
        if chart_data:
            chart_view = create_bar_chart(
                chart_data[:30], x_key="model", y_key="tokens",
                title="模型 Token 消耗排名 (Top 10)", y_label="Token", color="#c7a7ff"
            )
            self._current_chart_view = chart_view
            self.chart_layout.addWidget(chart_view)

        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)

    def update_data(self, data: dict):
        """接收新数据更新"""
        self._raw_data = data
        logs = data.get("logs", {})
        sessions = logs.get("sessions") or []

        projects = set()
        for s in sessions:
            p = s.get("project")
            if p:
                projects.add(str(p))

        cur_proj = self.combo_project.currentText()
        self.combo_project.blockSignals(True)
        self.combo_project.clear()
        self.combo_project.addItem("所有项目")
        for p in sorted(projects, key=lambda x: x.lower()):
            self.combo_project.addItem(p)

        idx = self.combo_project.findText(cur_proj)
        self.combo_project.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_project.blockSignals(False)

        self._on_project_changed(self.combo_project.currentText())

    def _highlight_bar(self, model_name, on: bool):
        if not model_name or not self._current_chart_view:
            return
        try:
            self._current_chart_view.highlight_category(model_name, on)
        except Exception:
            pass

    def _on_table_selection(self, selected, deselected):
        if self._current_chart_view:
            self._current_chart_view.reset_highlight()
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if rows:
            name = self.proxy_model.data(self.proxy_model.mapToSource(rows[0]))
            self._highlight_bar(name, True)

    def _on_table_entered(self, index):
        if not index.isValid():
            return
        if self._current_chart_view:
            self._current_chart_view.reset_highlight()
        name = self.proxy_model.data(index)
        self._highlight_bar(name, True)

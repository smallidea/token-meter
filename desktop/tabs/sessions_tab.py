# -*- coding: utf-8 -*-
"""会话列表标签页

提供按项目、按工具筛选，按关键词搜索，以及可排序的会话明细表格。
"""

import datetime
from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QTableView, QHeaderView, QAbstractItemView,
)


class NumericSortProxyModel(QSortFilterProxyModel):
    """支持数字数值和字符串正确排序与多维度过滤的代理模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_filter = ""
        self.runtime_filter = ""
        self.search_keyword = ""

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)

        if left_data is not None and right_data is not None:
            try:
                return float(left_data) < float(right_data)
            except (ValueError, TypeError):
                pass

        left_str = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole) or ""
        right_str = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return str(left_str).lower() < str(right_str).lower()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return True

        # 列定义: 0: 工具, 1: 项目, 2: 模型, 3: Token数, 4: 花费, 5: 开始时间, 6: 轮次
        runtime_item = model.item(source_row, 0)
        project_item = model.item(source_row, 1)
        model_item = model.item(source_row, 2)

        runtime_val = runtime_item.text() if runtime_item else ""
        project_val = project_item.text() if project_item else ""
        model_val = model_item.text() if model_item else ""

        # 工具过滤
        if self.runtime_filter and self.runtime_filter != "所有工具":
            if runtime_val != self.runtime_filter:
                return False

        # 项目过滤
        if self.project_filter and self.project_filter != "所有项目":
            if project_val != self.project_filter:
                return False

        # 关键词过滤 (项目/模型/工具/ID)
        if self.search_keyword:
            kw = self.search_keyword.lower()
            sess_id = model.item(source_row, 0).data(Qt.ItemDataRole.UserRole + 1) or ""
            text_corpus = f"{runtime_val} {project_val} {model_val} {sess_id}".lower()
            if kw not in text_corpus:
                return False

        return True


class SessionsTab(QWidget):
    """会话列表标签页"""

    HEADERS = ["工具", "项目", "模型", "Token 数", "花费", "开始时间", "对话轮次"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_sessions = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        # 项目下拉框
        toolbar.addWidget(QLabel("项目:"))
        self.combo_project = QComboBox()
        self.combo_project.addItem("所有项目")
        self.combo_project.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.combo_project)

        # 工具下拉框
        toolbar.addWidget(QLabel("工具:"))
        self.combo_runtime = QComboBox()
        self.combo_runtime.addItem("所有工具")
        self.combo_runtime.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.combo_runtime)

        # 搜索框
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("搜索项目 / 模型 / 会话 ID...")
        self.edit_search.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.edit_search)

        # 统计数量
        self.lbl_count = QLabel("共 0 个会话")
        self.lbl_count.setStyleSheet("color: #a8b3c1; font-weight: bold;")
        toolbar.addWidget(self.lbl_count)

        layout.addLayout(toolbar)

        # 数据模型与表格
        self.source_model = QStandardItemModel()
        self.source_model.setHorizontalHeaderLabels(self.HEADERS)

        self.proxy_model = NumericSortProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

    def _on_filter_changed(self):
        """筛选条件改变时触发重筛"""
        self.proxy_model.project_filter = self.combo_project.currentText()
        self.proxy_model.runtime_filter = self.combo_runtime.currentText()
        self.proxy_model.search_keyword = self.edit_search.text().strip()
        self.proxy_model.invalidateFilter()
        self._update_count_label()

    def _update_count_label(self):
        visible = self.proxy_model.rowCount()
        total = len(self._all_sessions)
        if visible == total:
            self.lbl_count.setText(f"共 {total} 个会话")
        else:
            self.lbl_count.setText(f"显示 {visible} / {total} 个会话")

    def update_data(self, data: dict):
        """更新会话表格数据"""
        logs = data.get("logs", {})
        sessions = logs.get("sessions") or []
        self._all_sessions = sessions

        # 收集去重项目与工具
        projects = set()
        runtimes = set()

        self.source_model.removeRows(0, self.source_model.rowCount())

        for s in sessions:
            runtime = str(s.get("runtime") or s.get("provider") or "未知")
            project = str(s.get("project") or "未分类")
            title = str(s.get("title") or s.get("session_name") or "")

            # 模型字段：支持 list 或 str
            models_val = s.get("models")
            if isinstance(models_val, list):
                model = ", ".join(str(m) for m in models_val if m)
            else:
                model = str(models_val or s.get("model") or "未知")

            tokens = int(s.get("tokens") or 0)
            cost = float(s.get("cost") or 0.0)
            turns = int(s.get("turns") or 0)
            sess_id = str(s.get("id") or "")

            # 开始时间字段：优先 start，其次 started
            started = s.get("start") or s.get("started")
            if started:
                try:
                    time_str = datetime.datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = str(started)
            else:
                time_str = "-"

            if project:
                projects.add(project)
            if runtime:
                runtimes.add(runtime)

            # 创建表格项
            item_runtime = QStandardItem(runtime)
            # 在 UserRole+1 存储用于搜索的全部文本（包含 ID 与标题）
            item_runtime.setData(f"{sess_id} {title}", Qt.ItemDataRole.UserRole + 1)

            item_project = QStandardItem(project)
            item_model = QStandardItem(model)

            item_tokens = QStandardItem(f"{tokens:,}")
            item_tokens.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_tokens.setData(tokens, Qt.ItemDataRole.UserRole)

            item_cost = QStandardItem(f"${cost:.4f}" if cost < 0.01 and cost > 0 else f"${cost:.2f}")
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_cost.setData(cost, Qt.ItemDataRole.UserRole)

            item_time = QStandardItem(time_str)
            item_time.setData(started or 0, Qt.ItemDataRole.UserRole)

            item_turns = QStandardItem(str(turns))
            item_turns.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_turns.setData(turns, Qt.ItemDataRole.UserRole)

            self.source_model.appendRow([
                item_runtime, item_project, item_model,
                item_tokens, item_cost, item_time, item_turns
            ])

        # 更新下拉框候选（保留当前选中项）
        cur_proj = self.combo_project.currentText()
        cur_rt = self.combo_runtime.currentText()

        self.combo_project.blockSignals(True)
        self.combo_project.clear()
        self.combo_project.addItem("所有项目")
        for p in sorted(projects, key=lambda x: x.lower()):
            self.combo_project.addItem(p)
        idx_p = self.combo_project.findText(cur_proj)
        self.combo_project.setCurrentIndex(idx_p if idx_p >= 0 else 0)
        self.combo_project.blockSignals(False)

        self.combo_runtime.blockSignals(True)
        self.combo_runtime.clear()
        self.combo_runtime.addItem("所有工具")
        for r in sorted(runtimes):
            self.combo_runtime.addItem(r)
        idx_r = self.combo_runtime.findText(cur_rt)
        self.combo_runtime.setCurrentIndex(idx_r if idx_r >= 0 else 0)
        self.combo_runtime.blockSignals(False)

        self._on_filter_changed()

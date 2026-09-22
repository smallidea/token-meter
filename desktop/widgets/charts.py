# -*- coding: utf-8 -*-
"""QtCharts 图表工厂

封装饼图、折线图、柱状图的创建逻辑，统一深色主题配色，并提供：
- hover 高亮 + tooltip
- 鼠标框选缩放（rubber band）+ 滚轮缩放
- 点击图例切换系列/扇区显隐
- 把内部 series/barset/categories 引用挂到 view 上供 tab 做联动
"""

from PySide6.QtCore import Qt, QPointF, QMargins, QTimer
from PySide6.QtGui import QColor, QPen, QFont, QPainter, QCursor
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QToolTip
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QLineSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis, QPieSlice, QLegendMarker,
)

# 模型配色轮转（12 种颜色）
MODEL_COLORS = [
    "#00bceb",  # 主色-青
    "#c7a7ff",  # 紫（花费）
    "#66d990",  # 绿
    "#ffb457",  # 橙
    "#ff6f6f",  # 红
    "#7fdbf2",  # 浅青
    "#1ba0e1",  # 深青
    "#e6a3ff",  # 浅紫
    "#5fd4a9",  # 薄荷
    "#ffd166",  # 金
    "#ff9eb7",  # 粉
    "#80e8ff",  # 冰蓝
]

# 主题常量
BG_COLOR = QColor("#0d1117")
PANEL_COLOR = QColor("#111820")
TEXT_COLOR = QColor("#f6f8fb")
DIM_COLOR = QColor("#a8b3c1")
FAINT_COLOR = QColor("#7d8ba0")
ACCENT_COLOR = QColor("#00bceb")
GRID_COLOR = QColor(27, 160, 225, 46)
HIGHLIGHT_COLOR = QColor("#ffffff")


class InteractiveChartView(QChartView):
    """支持框选缩放、滚轮缩放、高亮联动与全区域近邻捕捉 Tooltip 的图表视图"""

    def __init__(self, chart: QChart):
        super().__init__(chart)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)  # 开启全局鼠标追踪

        # 矩形框选缩放
        try:
            self.setRubberBand(QChartView.RubberBand.RectangleRubberBand)
        except Exception:
            self.setRubberBand(QChartView.RectangleRubberBand)

        # 供外部 tab 联动使用的引用
        self._chart_kind = None      # 'pie' | 'bar' | 'line'
        self._categories = []        # 分类名列表（bar/line）
        self._cat_index = {}          # 分类名 -> 索引
        self._bar_set = None          # 单系列柱状图的 QBarSet
        self._bar_base_color = None  # 柱子原色
        self._pie_slices = []         # QPieSlice 列表
        self._pie_names = []          # 与 slices 对齐的名字
        self._pie_values = []         # 与 slices 对齐的数值
        self._line_series = None
        self._line_points = []        # [(cat_label, value)]
        self._is_token_line = True
        self._highlighted_index = -1

    # ---- 丝滑 Tooltip 系统 ----
    def show_tooltip(self, text: str, local_pos: QPointF = None):
        """显示原生自适应边缘的高质感 tooltip，坐标绝对不偏移"""
        pos = QCursor.pos()
        pos.setX(pos.x() + 14)
        pos.setY(pos.y() + 14)
        QToolTip.showText(pos, text, self)

    def hide_tooltip(self):
        QToolTip.hideText()

    # ---- ECharts 级全区域近邻捕捉 (Nearest Neighbor Hit-testing) ----
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._chart_kind == "line" and self._line_points:
            pos = event.position() if hasattr(event, "position") else event.pos()
            chart = self.chart()
            if chart:
                plot_area = chart.plotArea()
                if plot_area.contains(pos):
                    val_pt = chart.mapToValue(pos)
                    idx = int(round(val_pt.x()))
                    if 0 <= idx < len(self._line_points):
                        cat, r_val = self._line_points[idx]
                        if self._is_token_line:
                            tip_text = f"{cat}\n{_fmt_tokens(r_val)} Token ({int(r_val):,})"
                        else:
                            tip_text = f"{cat}\n{_fmt_money(r_val)}"
                        self.show_tooltip(tip_text)
                        return
        if self._chart_kind == "line":
            self.hide_tooltip()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hide_tooltip()

    # ---- 滚轮缩放 ----
    def wheelEvent(self, event):
        try:
            delta = event.angleDelta().y()
        except AttributeError:
            delta = 0
        if delta == 0:
            super().wheelEvent(event)
            return
        factor = 1.25 if delta > 0 else 1 / 1.25
        self.chart().zoom(factor)
        event.accept()

    # ---- 外部联动：按分类名高亮 ----
    def highlight_category(self, name: str, on: bool):
        idx = self._cat_index.get(name)
        if idx is None:
            return
        if self._chart_kind == "bar" and self._bar_set is not None:
            if on:
                self._bar_set.setColor(QColor("#ffffff"))
            else:
                if self._bar_base_color is not None:
                    self._bar_set.setColor(self._bar_base_color)
        elif self._chart_kind == "pie" and 0 <= idx < len(self._pie_slices):
            self._pie_slices[idx].setExploded(on)
            if on:
                self._pie_slices[idx].setLabelVisible(True)

    def reset_highlight(self):
        if self._chart_kind == "bar" and self._bar_set is not None and self._bar_base_color is not None:
            self._bar_set.setColor(self._bar_base_color)
        elif self._chart_kind == "pie":
            for s in self._pie_slices:
                s.setExploded(False)


def _base_chart(title: str) -> QChart:
    """创建带深色主题的基础图表"""
    chart = QChart()
    chart.setTitle(title)
    chart.setBackgroundBrush(BG_COLOR)
    chart.setBackgroundRoundness(8)
    chart.setTitleBrush(TEXT_COLOR)
    chart.setTitleFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    chart.legend().setLabelColor(DIM_COLOR)
    chart.legend().setFont(QFont("Segoe UI", 9))
    chart.setMargins(QMargins(8, 8, 8, 8))
    chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
    return chart


def _interactive_view(chart: QChart) -> InteractiveChartView:
    view = InteractiveChartView(chart)
    return view


def _fmt_money(v: float) -> str:
    if 0 < v < 0.01:
        return f"${v:.4f}"
    return f"${v:.2f}"

def _fmt_tokens(n) -> str:
    """把 token 数换算成中文可读格式 (万/亿)"""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 100_000_000:
        return f"{n/100_000_000:.2f}亿"
    if n >= 10_000:
        return f"{n/10_000:.1f}万"
    return str(int(n))


def _toggle_marker_visible(marker: QLegendMarker, on: bool):
    """图例标记置灰/恢复样式"""
    try:
        f = marker.font()
        f.setStrikeOut(not on)
        marker.setFont(f)
        marker.setLabelBrush(FAINT_COLOR if not on else DIM_COLOR)
    except Exception:
        pass


def _wire_legend_toggle(chart: QChart, resolve):
    """点击图例切换系列/扇区显隐。

    某些 PySide6 构建的 QLegend 不暴露 clicked 信号；此时静默跳过，
    不影响其它交互。resolve(marker) -> toggle callable（调用即切换显隐）。
    """
    legend = chart.legend()
    if not hasattr(legend, "clicked"):
        return

    def _on_clicked(marker: QLegendMarker):
        try:
            toggle = resolve(marker)
            if toggle is None:
                return
            on = toggle()  # 返回切换后的可见性
            _toggle_marker_visible(marker, bool(on))
        except Exception:
            pass

    legend.clicked.connect(_on_clicked)


def create_pie_chart(data: list, title: str = "模型构成",
                     value_key: str = "cost") -> QChartView:
    """创建饼图：hover 放大 + tooltip（名称/数值/占比），点击图例切换显隐"""
    chart = _base_chart(title)
    series = QPieSeries()

    valid = [d for d in data if float(d.get(value_key) or 0) > 0]
    valid.sort(key=lambda d: float(d.get(value_key, 0)), reverse=True)
    total = sum(float(d.get(value_key, 0)) for d in valid) or 1.0

    view = _interactive_view(chart)
    view._chart_kind = "pie"

    for i, item in enumerate(valid[:30]):
        name = str(item.get("model", "未知"))
        value = float(item.get(value_key, 0))
        runtime = str(item.get("runtime") or "")
        label = f"{name} ({runtime})" if runtime else name
        s = series.append(label, value)
        s.setColor(QColor(MODEL_COLORS[i % len(MODEL_COLORS)]))
        s.setBorderColor(QColor(0, 0, 0, 80))
        s.setBorderWidth(1)
        pct = value / total * 100.0
        if pct > 10.0:
            s.setLabelVisible(True)
            s.setLabelColor(DIM_COLOR)
            s.setLabelFont(QFont("Segoe UI", 8))

        tip = f"{label}\n{_fmt_tokens(value)} tokens · {pct:.1f}%"
        view._pie_slices.append(s)
        view._pie_names.append(name)
        view._pie_values.append(value)
        view._cat_index[name] = len(view._cat_index)

        def _make_hover(slice_ref=s, tip_text=tip):
            def _hovered(on):
                slice_ref.setExplodeDistanceFactor(0.12 if on else 0.0)
                slice_ref.setExploded(on)
                if on:
                    view.show_tooltip(tip_text, view.mapFromGlobal(QCursor.pos()))
                else:
                    view.hide_tooltip()
            return _hovered
        s.hovered.connect(_make_hover())

    chart.addSeries(series)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)

    # 点击图例切换 slice 显隐（无信号构建自动跳过）
    def _resolve_pie(marker: QLegendMarker):
        try:
            if marker.markerType() == QLegendMarker.LegendMarkerType.PieMarker:
                sl = marker.slice()

                def _toggle():
                    sl.setVisible(not sl.isVisible())
                    return sl.isVisible()
                return _toggle
        except Exception:
            pass
        return None
    _wire_legend_toggle(chart, _resolve_pie)

    return view


def create_line_chart(data: list, x_key: str, y_key: str,
                      title: str = "趋势", y_label: str = "") -> QChartView:
    """创建折线图：修复X轴唯一类别映射、Y轴智能量级自适应与紧凑留白、数据点 hover tooltip"""
    chart = _base_chart(title)
    series = QLineSeries()
    series.setName(y_label or y_key)
    series.setPen(QPen(ACCENT_COLOR, 2))
    series.setPointsVisible(True)
    series.setMarkerSize(8)

    view = _interactive_view(chart)
    view._chart_kind = "line"
    view._line_series = series
    view._is_token_line = "token" in y_label.lower()

    if not data:
        chart.addSeries(series)
        chart.legend().hide()
        return view

    raw_categories = []
    raw_values = []
    for item in data:
        raw_categories.append(str(item.get(x_key, "")))
        raw_values.append(float(item.get(y_key, 0)))

    # 1. 智能量级自适应（亿 / 万 / 原始）
    max_val = max(raw_values) if raw_values else 0.0
    is_token = "token" in y_label.lower()

    if is_token:
        if max_val >= 100_000_000:
            unit_scale = 100_000_000.0
            display_y_label = f"{y_label}（亿）"
        elif max_val >= 10_000:
            unit_scale = 10_000.0
            display_y_label = f"{y_label}（万）"
        else:
            unit_scale = 1.0
            display_y_label = y_label
    else:
        unit_scale = 1.0
        display_y_label = y_label

    scaled_values = [v / unit_scale for v in raw_values]

    for i, s_val in enumerate(scaled_values):
        series.append(QPointF(i, s_val))
        view._line_points.append((raw_categories[i], raw_values[i]))

    chart.addSeries(series)

    # 2. X 轴构建：避免 QBarCategoryAxis 对重复字符串去重合并导致轴坍塌
    # 使用零宽空格保证每个分类唯一，从而使所有数据点严格 1:1 精确映射
    axis_x = QBarCategoryAxis()
    step = max(1, len(raw_categories) // 8)
    display_cats = []
    for i, cat in enumerate(raw_categories):
        short_cat = cat[-5:] if len(cat) >= 5 else cat
        if i % step == 0 or i == len(raw_categories) - 1:
            display_cats.append(short_cat)
        else:
            display_cats.append("\u200b" * (i + 1))
    axis_x.append(display_cats)
    axis_x.setLabelsColor(FAINT_COLOR)
    axis_x.setLabelsFont(QFont("Segoe UI", 8))
    axis_x.setLabelsAngle(-45)  # 倾斜展示，彻底消除省略号 ...
    axis_x.setGridLineColor(GRID_COLOR)
    axis_x.setLineVisible(False)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    # 3. Y 轴紧凑范围计算：彻底消灭上部多余空白
    axis_y = QValueAxis()
    axis_y.setTitleText(display_y_label)
    axis_y.setTitleBrush(DIM_COLOR)
    axis_y.setLabelsColor(FAINT_COLOR)
    axis_y.setLabelsFont(QFont("Segoe UI", 8))
    axis_y.setGridLineColor(GRID_COLOR)
    axis_y.setLineVisible(False)

    scaled_max = (max_val / unit_scale) if unit_scale > 0 else 1.0
    # 顶部预留 15% 呼吸空间，让最高波峰饱满充盈画面的 85% 高度
    y_upper = scaled_max * 1.15 if scaled_max > 0 else 1.0
    axis_y.setRange(0, y_upper)

    if scaled_max >= 10:
        axis_y.setLabelFormat("%.1f")
    elif scaled_max >= 1:
        axis_y.setLabelFormat("%.2f")
    else:
        axis_y.setLabelFormat("%.3f" if not is_token else "%.0f")

    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    # 4. hover 数据点 tooltip：自适应格式化显示
    def _hovered(point: QPointF, on: bool):
        idx = int(round(point.x()))
        if 0 <= idx < len(view._line_points):
            cat, r_val = view._line_points[idx]
            if on:
                if is_token:
                    tip_text = f"{cat}\n{_fmt_tokens(r_val)} Token ({int(r_val):,})"
                else:
                    tip_text = f"{cat}\n{_fmt_money(r_val)}"
                view.show_tooltip(tip_text, view.mapFromGlobal(QCursor.pos()))
            else:
                view.hide_tooltip()
    series.hovered.connect(_hovered)

    chart.legend().hide()
    return view


def create_bar_chart(data: list, x_key: str, y_key: str,
                     title: str = "统计", y_label: str = "",
                     color: str = "#00bceb") -> QChartView:
    """创建柱状图：柱子 hover 高亮 + tooltip，框选 + 滚轮缩放，图例切换"""
    chart = _base_chart(title)
    bar_set = QBarSet(y_label or y_key)
    base_color = QColor(color)
    bar_set.setColor(base_color)
    bar_set.setBorderColor(QColor(0, 0, 0, 60))

    view = _interactive_view(chart)
    view._chart_kind = "bar"
    view._bar_set = bar_set
    view._bar_base_color = base_color

    categories = []
    for item in data:
        label = str(item.get(x_key, ""))
        if len(label) > 20:
            label = label[:18] + "…"
        categories.append(label)
        bar_set.append(float(item.get(y_key, 0)))
        view._cat_index[label] = len(view._cat_index)
    view._categories = categories

    series = QBarSeries()
    series.append(bar_set)
    series.setBarWidth(0.6)
    chart.addSeries(series)

    axis_x = QBarCategoryAxis()
    axis_x.append(categories)
    axis_x.setLabelsColor(FAINT_COLOR)
    axis_x.setLabelsFont(QFont("Segoe UI", 8))
    axis_x.setLabelsAngle(-45 if len(categories) > 6 else 0)
    axis_x.setGridLineColor(GRID_COLOR)
    axis_x.setLineVisible(False)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    axis_y.setTitleText(y_label)
    axis_y.setTitleBrush(DIM_COLOR)
    axis_y.setLabelsColor(FAINT_COLOR)
    axis_y.setLabelsFont(QFont("Segoe UI", 8))
    axis_y.setGridLineColor(GRID_COLOR)
    axis_y.setLineVisible(False)
    values = [float(item.get(y_key, 0)) for item in data]
    max_val = max(values) if values else 1.0
    axis_y.setRange(0, max_val * 1.15 if max_val > 0 else 1)
    if "cost" in y_label.lower() or "$" in y_label:
        axis_y.setLabelFormat("$%.2f" if max_val < 100 else "$%.0f")
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    # 柱子 hover 高亮 + tooltip
    def _hovered(on: bool, index: int, barset: QBarSet):
        if on:
            barset.setColor(HIGHLIGHT_COLOR)
            if 0 <= index < len(categories):
                view.show_tooltip(
                    f"{categories[index]}\n{_fmt_tokens(values[index])}",
                    view.mapFromGlobal(QCursor.pos()),
                )
        else:
            barset.setColor(base_color)
            view.hide_tooltip()
    bar_set.hovered.connect(_hovered)

    # 点击图例切换系列显隐（无信号构建自动跳过）
    def _resolve_bar(marker: QLegendMarker):
        try:
            sl = marker.series()

            def _toggle():
                sl.setVisible(not sl.isVisible())
                return sl.isVisible()
            return _toggle
        except Exception:
            pass
        return None
    _wire_legend_toggle(chart, _resolve_bar)

    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
    return view

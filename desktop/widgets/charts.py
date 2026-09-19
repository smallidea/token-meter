# -*- coding: utf-8 -*-
"""QtCharts 图表工厂

封装饼图、折线图、柱状图的创建逻辑，统一深色主题配色。
"""

from PySide6.QtCore import Qt, QPointF, QMargins
from PySide6.QtGui import QColor, QPen, QFont, QLinearGradient, QPainter
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QLineSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis, QDateTimeAxis, QPieSlice,
)

# 模型配色轮转（8 种颜色）
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


def _chart_view(chart: QChart) -> QChartView:
    """创建图表视图"""
    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setStyleSheet("background: transparent; border: none;")
    return view


def create_pie_chart(data: list, title: str = "模型构成",
                     value_key: str = "cost") -> QChartView:
    """创建饼图

    Args:
        data: list of dict，每项包含 'model' 和 value_key 对应的数值
        title: 图表标题
        value_key: 数值字段名（'cost' 或 'tokens'）
    """
    chart = _base_chart(title)
    series = QPieSeries()

    # 过滤零值并按值排序
    valid = [d for d in data if float(d.get(value_key) or 0) > 0]
    valid.sort(key=lambda d: float(d.get(value_key, 0)), reverse=True)

    for i, item in enumerate(valid[:12]):  # 最多显示 12 个
        name = str(item.get("model", "未知"))
        value = float(item.get(value_key, 0))
        s = series.append(name, value)
        s.setColor(QColor(MODEL_COLORS[i % len(MODEL_COLORS)]))
        s.setBorderColor(QColor(0, 0, 0, 80))
        s.setBorderWidth(1)
        # 占比超过 10% 的显示标签
        if valid and value / sum(float(d.get(value_key, 0)) for d in valid) > 0.10:
            s.setLabelVisible(True)
            s.setLabelColor(DIM_COLOR)
            s.setLabelFont(QFont("Segoe UI", 8))

    chart.addSeries(series)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
    return _chart_view(chart)


def create_line_chart(data: list, x_key: str, y_key: str,
                      title: str = "趋势", y_label: str = "") -> QChartView:
    """创建折线图（带渐变填充）

    Args:
        data: list of dict，按 x_key 排序
        x_key: X 轴字段名（通常是 'day'，ISO 日期字符串）
        y_key: Y 轴字段名（如 'cost', 'tokens'）
    """
    chart = _base_chart(title)
    series = QLineSeries()
    series.setName(y_label or y_key)
    series.setPen(QPen(ACCENT_COLOR, 2))

    if not data:
        chart.addSeries(series)
        return _chart_view(chart)

    # 构建数据点
    categories = []
    values = []
    for item in data:
        categories.append(str(item.get(x_key, "")))
        values.append(float(item.get(y_key, 0)))

    for i, val in enumerate(values):
        series.append(QPointF(i, val))

    chart.addSeries(series)

    # X 轴 — 使用分类
    axis_x = QBarCategoryAxis()
    # 只显示部分标签避免拥挤
    step = max(1, len(categories) // 8)
    display_cats = []
    for i, cat in enumerate(categories):
        if i % step == 0 or i == len(categories) - 1:
            # 只显示月-日
            display_cats.append(cat[-5:] if len(cat) >= 5 else cat)
        else:
            display_cats.append("")
    axis_x.append(categories)
    axis_x.setLabelsColor(FAINT_COLOR)
    axis_x.setLabelsFont(QFont("Segoe UI", 8))
    axis_x.setGridLineColor(GRID_COLOR)
    axis_x.setLineVisible(False)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    # Y 轴
    axis_y = QValueAxis()
    axis_y.setTitleText(y_label)
    axis_y.setTitleBrush(DIM_COLOR)
    axis_y.setLabelsColor(FAINT_COLOR)
    axis_y.setLabelsFont(QFont("Segoe UI", 8))
    axis_y.setGridLineColor(GRID_COLOR)
    axis_y.setLineVisible(False)
    max_val = max(values) if values else 1
    axis_y.setRange(0, max_val * 1.15)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    chart.legend().hide()
    return _chart_view(chart)


def create_bar_chart(data: list, x_key: str, y_key: str,
                     title: str = "统计", y_label: str = "",
                     color: str = "#00bceb") -> QChartView:
    """创建柱状图

    Args:
        data: list of dict
        x_key: 分类字段名
        y_key: 数值字段名
    """
    chart = _base_chart(title)
    bar_set = QBarSet(y_label or y_key)
    bar_set.setColor(QColor(color))
    bar_set.setBorderColor(QColor(0, 0, 0, 60))

    categories = []
    for item in data:
        label = str(item.get(x_key, ""))
        # 截断过长的标签
        if len(label) > 20:
            label = label[:18] + "…"
        categories.append(label)
        bar_set.append(float(item.get(y_key, 0)))

    series = QBarSeries()
    series.append(bar_set)
    series.setBarWidth(0.6)
    chart.addSeries(series)

    # X 轴
    axis_x = QBarCategoryAxis()
    axis_x.append(categories)
    axis_x.setLabelsColor(FAINT_COLOR)
    axis_x.setLabelsFont(QFont("Segoe UI", 8))
    axis_x.setLabelsAngle(-45 if len(categories) > 6 else 0)
    axis_x.setGridLineColor(GRID_COLOR)
    axis_x.setLineVisible(False)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    # Y 轴
    axis_y = QValueAxis()
    axis_y.setTitleText(y_label)
    axis_y.setTitleBrush(DIM_COLOR)
    axis_y.setLabelsColor(FAINT_COLOR)
    axis_y.setLabelsFont(QFont("Segoe UI", 8))
    axis_y.setGridLineColor(GRID_COLOR)
    axis_y.setLineVisible(False)
    values = [float(item.get(y_key, 0)) for item in data]
    max_val = max(values) if values else 1
    axis_y.setRange(0, max_val * 1.15)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    chart.legend().hide()
    return _chart_view(chart)

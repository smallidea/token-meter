# -*- coding: utf-8 -*-
"""Windows 桌面版 UI / UX 自动化冒烟测试"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# 必须存在一个全局 QApplication 实例
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from desktop.main_window import MainWindow
from desktop.widgets.session_detail_dialog import SessionDetailDialog
from desktop.tabs.overview_tab import OverviewTab
from desktop.tabs.sessions_tab import SessionsTab


class DesktopUiTests(unittest.TestCase):

    def setUp(self):
        self.mock_data = {
            "cross": {
                "total_sessions": 12,
                "total_cost": 15.68,
                "total_tokens": 1580000,
                "total_executions": 45,
                "model_mix": [
                    {"model": "claude-3-7-sonnet", "tokens": 1200000, "cost": 12.5},
                    {"model": "gpt-4o", "tokens": 380000, "cost": 3.18},
                ],
                "providers": [
                    {"provider": "cursor", "sessions": 8},
                    {"provider": "claude", "sessions": 4},
                ],
            },
            "logs": {
                "sessions": [
                    {
                        "id": "test-sess-cursor-12345",
                        "runtime": "cursor",
                        "project": "D:/workspace/my-project",
                        "model": "claude-3-7-sonnet",
                        "tokens": 250000,
                        "cost": 2.50,
                        "turns": 15,
                        "start": 1726000000,
                        "title": "Cursor 开发调试",
                    },
                    {
                        "id": "test-sess-claude-67890",
                        "runtime": "claude",
                        "project": "D:/workspace/backend",
                        "model": "claude-3-5-sonnet",
                        "tokens": 80000,
                        "cost": 0.80,
                        "turns": 6,
                        "start": 1726010000,
                        "title": "Claude 辅助重构",
                    }
                ]
            }
        }

    def test_main_window_instantiation_and_tabs(self):
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window._tabs.count(), 5)
        # 测试数据更新分发
        window._on_data_ready(self.mock_data)
        window.close()

    def test_session_detail_dialog(self):
        sess_data = self.mock_data["logs"]["sessions"][0]
        dlg = SessionDetailDialog(sess_data)
        self.assertIsNotNone(dlg)
        self.assertIn("Cursor", dlg.windowTitle())
        dlg.close()

    def test_sessions_tab_filtering_and_count(self):
        tab = SessionsTab()
        tab.update_data(self.mock_data)
        self.assertEqual(tab.proxy_model.rowCount(), 2)

        # 测试关键词搜索过滤
        tab.edit_search.setText("cursor")
        self.assertEqual(tab.proxy_model.rowCount(), 1)

        # 测试重置筛选
        tab._reset_filters()
        self.assertEqual(tab.proxy_model.rowCount(), 2)
        tab.close()

    def test_line_chart_scale_and_categories(self):
        from desktop.widgets.charts import create_line_chart
        from PySide6.QtCharts import QBarCategoryAxis, QValueAxis

        # 测试大量数据点与亿级数值
        data = [
            {"day": f"2026-08-{i:02d}", "tokens": 10_000_000 * i}
            for i in range(1, 31)
        ]
        chart_view = create_line_chart(data, "day", "tokens", "测试趋势", "Token")
        self.assertIsNotNone(chart_view)

        chart = chart_view.chart()
        axes_x = [a for a in chart.axes() if isinstance(a, QBarCategoryAxis)]
        axes_y = [a for a in chart.axes() if isinstance(a, QValueAxis)]

        self.assertEqual(len(axes_x), 1)
        self.assertEqual(len(axes_y), 1)

        # 验证分类数量严格等于数据点数量（零宽空格未被合并）
        self.assertEqual(axes_x[0].count(), 30)
        # 验证Y轴自动切换为亿并合理紧凑留白（最大 3 亿 * 1.15 = 3.45 亿）
        self.assertIn("亿", axes_y[0].titleText())
        self.assertAlmostEqual(axes_y[0].max(), 3.0 * 1.15, places=2)

    def test_overview_tab_range_switching_and_filtering(self):
        from desktop.tabs.overview_tab import OverviewTab
        tab = OverviewTab()
        # 注入包含非法日期和大量日期的测试数据
        mock_with_bad_dates = {
            "cross": {
                "total_cost": 10.0, "total_tokens": 5000000,
                "total_sessions": 5, "total_executions": 10,
                "model_mix": []
            },
            "logs": {
                "sessions": [
                    {"start": "invalid_date", "tokens": 99999999},
                    {"start": 1726000000, "tokens": 1000},
                    {"start": 1726086400, "tokens": 2000},
                ]
            }
        }
        tab.update_data(mock_with_bad_dates)
        # 验证脏数据被过滤，有效日期保留
        self.assertTrue(hasattr(tab, "_full_daily"))
        days = [d["day"] for d in tab._full_daily]
        self.assertNotIn("?", days)
        self.assertNotIn("invalid_date", days)

        # 测试切换时间范围胶囊
        tab._on_range_changed(14)
        self.assertEqual(tab._selected_days_limit, 14)
        tab.close()


if __name__ == "__main__":
    unittest.main()

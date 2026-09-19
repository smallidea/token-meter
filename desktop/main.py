#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Token Meter 桌面端入口

初始化流程：
1. 设置工作目录和 sys.path
2. 调用 custom.patcher.apply_patches()（注册适配器 + 路径归一化，但不启动 HTTP 服务）
3. 创建 QApplication 并显示主窗口
"""

import os
import sys

# 切换工作目录到 token-meter 根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 应用自定义补丁（注册适配器 + 路径归一化）
from custom.patcher import apply_patches
apply_patches()

# 导入 Qt（必须在 apply_patches 之后，因为数据层需要初始化）
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from desktop.main_window import MainWindow


def main():
    """启动桌面端应用"""
    # 高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Token Meter")
    app.setOrganizationName("TokenMeter")

    # 深色模式提示（Windows 11+）
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

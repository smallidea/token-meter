#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token Meter 扩展启动入口
=======================
包含界面全中文汉化支持，以及 Trae CN、WorkBuddy、Antigravity 适配器扩展。
由于本文件独立于官方 git 跟踪列表，后续 git pull 升级不会被覆盖。
"""

import os
import sys

# 切换工作目录到当前文件所在目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 应用自定义补丁与适配器
from custom.patcher import apply_patches
apply_patches()

# 启动官方应用主服务
from token_meter import app

if __name__ == "__main__":
    app.main()

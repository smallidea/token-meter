# -*- coding: utf-8 -*-
"""Windows 磁盘编号与项目路径归一化工具模块

解决因 Windows 盘符大小写不一致（例如 d:/ 与 D:/、c:/ 与 C:/）、
斜杠反斜杠混用、以及部分工具截断或丢失盘符冒号（如 d/projects/...）
导致的前端下拉框重复、数据拆分和聚合不匹配问题。
"""

import os
import re


def normalize_project(val):
    """规范化项目路径和磁盘盘符：
    1. 去除首尾空白，统一将反斜杠 '\\' 替换为正斜杠 '/'
    2. 去除协议前缀（如 file:///）
    3. 修复丢失冒号的盘符路径（如 d/projects/... -> D:/projects/...）
    4. 统一 Windows 盘符为大写字母（如 d:/... -> D:/...，c:/... -> C:/...）
    5. 统一将当前用户主目录匹配并简写为 '~'（大小写不敏感匹配）
    6. 去除末尾冗余斜杠（根盘符如 D:/ 除外）
    """
    if not val:
        return ""
    p = str(val).strip().replace("\\", "/")

    # 去除 URL / file 协议前缀
    if p.startswith("file:///"):
        p = p[8:]
    elif p.startswith("file://"):
        p = p[7:]

    # 修复类似 "d/projects/..." 或 "c/users/..."（Windows丢失冒号的盘符）
    if len(p) >= 2 and p[0].isalpha() and p[1] == "/":
        p = p[0].upper() + ":/" + p[2:]
    # 统一盘符大写并保证冒号后接正斜杠
    elif len(p) >= 2 and p[0].isalpha() and p[1] == ":":
        p = p[0].upper() + ":" + (p[2:] if len(p) > 2 else "")
        if len(p) >= 3 and p[2] != "/":
            p = p[:2] + "/" + p[2:]

    # 智能匹配用户主目录并替换为 '~'（大小写不敏感匹配）
    home = os.path.expanduser("~").replace("\\", "/")
    if len(home) >= 2 and home[0].isalpha() and home[1] == ":":
        home_norm = home[0].upper() + home[1:]
    else:
        home_norm = home

    if p.lower().startswith(home_norm.lower()):
        p = "~" + p[len(home_norm):]

    # 去除末尾冗余正斜杠（保留根盘符如 "D:/"）
    if len(p) > 3 and p.endswith("/"):
        p = p.rstrip("/")

    return p

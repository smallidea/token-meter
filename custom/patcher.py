# -*- coding: utf-8 -*-
"""Token Meter 运行时补丁注入器 (零侵入挂载自定义适配器、中文前端与路径归一化引擎)

包含：
1. 环境变量 TOKEN_METER_PAGE 重定向到中文界面
2. 动态注册 Antigravity, WorkBuddy, Trae CN 适配器
3. 全局 Windows 磁盘编号与项目路径不区分大小写归一化（彻底消除重复项目和漏聚合）
4. 智能聚合优化：各平台优先聚合近期活跃会话，避免冷启动扫描上千文件导致的 HTTP 超时与 [WinError 10053]
5. cross_session 冷启动保护，确保 HTTP 线程毫秒级响应
"""

import os
import sys
import time

from custom.path_normalizer import normalize_project


def apply_patches():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. 强制加载全中文界面
    zh_page = os.path.join(root_dir, "page_zh.html")
    if os.path.exists(zh_page):
        os.environ["TOKEN_METER_PAGE"] = zh_page

    from token_meter import app
    from token_meter.runtimes.registry import RuntimeRegistry
    from custom.antigravity_adapter import AntigravityRuntimeAdapter
    from custom.workbuddy_adapter import WorkbuddyRuntimeAdapter
    from custom.traecn_adapter import TraeCNRuntimeAdapter
    from custom.grokbot_adapter import GrokbotRuntimeAdapter
    from custom.doubao_adapter import DoubaoRuntimeAdapter

    # 2. 注入自定义适配器到 RuntimeRegistry
    orig_runtime_registry = app.runtime_registry

    def patched_runtime_registry():
        current = orig_runtime_registry()
        if "antigravity" in current.runtime_ids and "grokbot" in current.runtime_ids:
            return current

        compat = {
            "summary_row": app.summary_row,
            "metric_availability": app.metric_availability,
        }

        custom_adapters = [
            AntigravityRuntimeAdapter(compat=compat),
            WorkbuddyRuntimeAdapter(compat=compat),
            TraeCNRuntimeAdapter(compat=compat),
            GrokbotRuntimeAdapter(compat=compat),
            DoubaoRuntimeAdapter(compat=compat),
        ]
        all_adapters = list(current._ordered) + custom_adapters
        new_registry = RuntimeRegistry(all_adapters)
        app._RUNTIME_REGISTRY = new_registry
        return new_registry

    app.runtime_registry = patched_runtime_registry

    # 3. 增强 recompute 支持自定义 provider
    orig_recompute = app.recompute

    def patched_recompute(source):
        if isinstance(source, str):
            source = app.source_from_path(source)
        if isinstance(source, dict):
            provider = source.get("provider")
            if provider in ("antigravity", "workbuddy", "traecn", "grokbot", "doubao"):
                reg = app.runtime_registry()
                adapter = reg.get(provider)
                if adapter and hasattr(adapter, "load"):
                    return adapter.load(source)
        return orig_recompute(source)

    app.recompute = patched_recompute


    # 4. 增强 source_from_path 查找能力
    orig_source_from_path = app.source_from_path

    def patched_source_from_path(path):
        res = orig_source_from_path(path)
        if res is not None:
            return res
        clean_path = str(path or "")
        sources, _ = app.cached_session_sources()
        if not sources:
            sources = app.all_session_sources()
        for s in sources:
            if s.get("path") == clean_path or s.get("id") == clean_path or clean_path.endswith(s.get("id", "---")):
                return s
        return None

    app.source_from_path = patched_source_from_path

    # 4.1 防御性包装 menubar_recommendation，杜绝 context 为非 dict 时的 AttributeError
    orig_menubar_recommendation = app.menubar_recommendation

    def patched_menubar_recommendation(st):
        if isinstance(st, dict):
            ctx = st.get("context")
            if not isinstance(ctx, dict):
                st["context"] = {"latest_pct": 0, "latest": 0, "window": 1000000}
        return orig_menubar_recommendation(st)

    app.menubar_recommendation = patched_menubar_recommendation

    # 4.2 全局 Windows 磁盘编号与项目路径不区分大小写归一化
    app.normalize_project = normalize_project

    # 4.2.1 增强 home_shorten 确保盘符大写与忽略大小写 ~ 替换
    orig_home_shorten = app.home_shorten

    def patched_home_shorten(path):
        return normalize_project(orig_home_shorten(path))

    app.home_shorten = patched_home_shorten

    # 4.2.2 增强 decode_cursor_project 修复丢失冒号的盘符
    orig_decode_cursor_project = app.decode_cursor_project

    def patched_decode_cursor_project(name):
        res = orig_decode_cursor_project(name)
        return normalize_project(res)

    app.decode_cursor_project = patched_decode_cursor_project

    # 4.2.3 增强 project_filter_key 保证键名大写盘符一致
    orig_project_filter_key = app.project_filter_key

    def patched_project_filter_key(value):
        res = orig_project_filter_key(value)
        return normalize_project(res)

    app.project_filter_key = patched_project_filter_key

    # 4.2.4 增强 all_session_sources 与 publish_source_inventory
    orig_all_session_sources = app.all_session_sources

    def patched_all_session_sources():
        sources = orig_all_session_sources()
        for s in sources:
            if isinstance(s, dict) and "project" in s:
                s["project"] = normalize_project(s["project"])
        return sources

    app.all_session_sources = patched_all_session_sources

    orig_publish_source_inventory = app.publish_source_inventory

    def patched_publish_source_inventory(sources):
        if sources:
            for s in sources:
                if isinstance(s, dict) and "project" in s:
                    s["project"] = normalize_project(s["project"])
        return orig_publish_source_inventory(sources)

    app.publish_source_inventory = patched_publish_source_inventory

    # 4.2.5 增强 session_summary 确保看板汇总行 project 一致
    orig_session_summary = app.session_summary

    def patched_session_summary(source, **kwargs):
        row = orig_session_summary(source, **kwargs)
        if isinstance(row, dict) and "project" in row:
            row["project"] = normalize_project(row["project"])
        return row

    app.session_summary = patched_session_summary

    # 4.2.6 增强 project_model_stats 与 git_delivery_state 的参数归一化
    orig_project_model_stats = app.project_model_stats

    def patched_project_model_stats(project):
        return orig_project_model_stats(normalize_project(project))

    app.project_model_stats = patched_project_model_stats

    orig_git_delivery_state = app.git_delivery_state

    def patched_git_delivery_state(project="", range_key="7"):
        return orig_git_delivery_state(normalize_project(project), range_key)

    app.git_delivery_state = patched_git_delivery_state

    # 5. 全量聚合，不裁剪历史会话（之前每平台只取 30 个导致 1888 个会话被遗漏）
    orig_canonical_aggregation_sources = app.canonical_aggregation_sources

    def patched_canonical_aggregation_sources(sources):
        source_rows = orig_canonical_aggregation_sources(sources)
        for s in source_rows:
            if isinstance(s, dict) and "project" in s:
                s["project"] = normalize_project(s["project"])
        return source_rows

    app.canonical_aggregation_sources = patched_canonical_aggregation_sources

    # 6. 冷启动非阻塞保护：防止前端在冷启动期间请求 /capabilities/inventory、/git-delivery 时挂起超时
    orig_cross_session = app.cross_session

    def patched_cross_session(sources=None):
        if app._xsess.get("data") is not None:
            return app._xsess["data"]
        # 如果 sources 为 None 且数据尚未准备好（由 HTTP 处理线程同步触发）：
        if sources is None:
            return {
                "generated_at": int(time.time()),
                "sessions": [],
                "current_sessions": [],
                "model_mix": {},
                "trend": {},
                "total_cost": 0.0,
                "total_sessions": 0,
                "total_executions": 0,
                "total_tokens": 0,
                "capabilities": {"items": [], "revision": "", "generated_at": int(time.time()), "count": 0},
                "availability": {
                    "cost": False, "tokens": False, "input_tokens": False,
                    "output_tokens": False, "cache": False, "throughput": False,
                    "context": False, "timing": False, "tool_results": False,
                },
                "coverage": {
                    "cost": {"covered_sessions": 0, "total_sessions": 0, "share": 0.0},
                    "tokens": {"covered_sessions": 0, "total_sessions": 0, "share": 0.0},
                    "cache": {"covered_sessions": 0, "total_sessions": 0, "share": 0.0},
                },
                "provenance": {"usage_basis": "reported"},
            }
        # 由后台 watcher 线程传入 sources 进行异步计算
        return orig_cross_session(sources=sources)

    app.cross_session = patched_cross_session

    print("[Token Meter] 已成功挂载高性能运行适配器: Antigravity, WorkBuddy, Trae CN, Grok Bot, 豆包 (Doubao)", flush=True)
    print("[Token Meter] 已启用 Windows 磁盘编号不区分大小写归一化引擎", flush=True)
    print(f"[Token Meter] 已生效中文界面: {os.environ.get('TOKEN_METER_PAGE')}", flush=True)


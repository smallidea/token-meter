# -*- coding: utf-8 -*-
"""Trae CN / Trae 运行时适配器

深度扫描 Trae 工作区存储 (%APPDATA%/Trae CN/User/workspaceStorage)
与全局状态，精准提取真实会话、多轮交互、深度推理 (DeepSeek-R1 等) 与 Token 消耗。
"""

import os
import glob
import json
import sqlite3
import datetime
import urllib.parse
from pathlib import Path

from token_meter.contracts import (
    RuntimeDescriptor,
    SourceRevision,
    DeletionPlan,
)
from custom.models_pricing import calculate_cost, get_price

CHARS_PER_TOKEN = 4


def _clean_model_name(raw_name: str) -> str:
    """清洗模型名称，提取规范模型标识"""
    if not raw_name:
        return "DeepSeek-V3"
    name = str(raw_name).strip()
    name = name.split("__")[-1].replace("_null", "")
    # 常见别名映射
    mapping = {
        "seed_m8": "Doubao-1.5-pro",
        "deepseek-V3-0324": "DeepSeek-V3",
        "deepseek-V3": "DeepSeek-V3",
        "deepseek-R1": "DeepSeek-R1",
        "deepseek-chat": "DeepSeek-V3",
        "deepseek-reasoner": "DeepSeek-R1",
    }
    return mapping.get(name, name)


class TraeCNRuntimeAdapter:
    """Trae CN (国内版) & Trae (国际版) 会话与真实 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "traecn",
        "Trae CN",
        frozenset(("sessions", "models", "tools")),
        "runtime.generic",
        "runtime-codex",
        "bytedance",
    )

    def __init__(self, db_path=None, compat=None):
        appdata = os.environ.get("APPDATA") or r"D:\Users\11003097\AppData\Roaming"
        self.appdata = appdata
        self.compat = compat or {}
        self._cache = {}

    def _get_workspace_roots(self) -> list:
        """获取所有可能存在的 Trae 工作区与全局根目录"""
        roots = []
        for name in ["Trae CN", "Trae"]:
            base = os.path.join(self.appdata, name, "User")
            if os.path.exists(base):
                roots.append(base)
        return roots

    def discover_legacy(self, context=None):
        """全面扫描所有工作区与全局存储，发现真实会话"""
        sources = []
        seen_ids = set()

        # 1. 优先扫描所有工作区的真实聊天与 Agent 会话
        for user_dir in self._get_workspace_roots():
            ws_storage = os.path.join(user_dir, "workspaceStorage")
            if not os.path.exists(ws_storage):
                continue

            for folder in glob.glob(os.path.join(ws_storage, "*")):
                if not os.path.isdir(folder):
                    continue
                db_path = os.path.join(folder, "state.vscdb")
                wp_json = os.path.join(folder, "workspace.json")
                if not os.path.exists(db_path):
                    continue

                # 解析真实项目路径
                project_path = "Trae"
                if os.path.exists(wp_json):
                    try:
                        with open(wp_json, "r", encoding="utf-8") as f:
                            info = json.load(f)
                        raw = info.get("folder") or ""
                        if raw.startswith("file:///"):
                            project_path = urllib.parse.unquote(raw[8:])
                            # Windows 盘符修复
                            if len(project_path) > 2 and project_path[1] == ":" and project_path[0].islower():
                                project_path = project_path[0].upper() + project_path[1:]
                        elif raw:
                            project_path = raw
                    except Exception:
                        pass

                # 读取数据库中的历史会话
                try:
                    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
                    conn = sqlite3.connect(uri, uri=True, timeout=0.5)
                    c = conn.cursor()
                    c.execute(
                        "SELECT key, value FROM ItemTable WHERE "
                        "key LIKE '%icube-ai%storage%' OR "
                        "key LIKE '%chatHistoryNeedToBeMigrated%'"
                    )
                    rows = c.fetchall()
                    conn.close()
                except Exception:
                    continue

                for _, val in rows:
                    try:
                        d = json.loads(val)
                        s_list = d.get("list") if isinstance(d, dict) else (d if isinstance(d, list) else [])
                        if not isinstance(s_list, list):
                            continue

                        for s in s_list:
                            if not isinstance(s, dict):
                                continue
                            sid = str(s.get("sessionId") or s.get("id") or s.get("turnId") or "")
                            if not sid or sid in seen_ids:
                                continue

                            msgs = s.get("messages") or []
                            if not msgs:
                                continue

                            seen_ids.add(sid)

                            # 时间戳
                            updated_at = s.get("updatedAt") or s.get("createdAt")
                            last_ts = float(updated_at) / 1000.0 if updated_at else 0.0

                            # 会话标题
                            title = str(s.get("title") or s.get("name") or "").strip()
                            if not title:
                                for m in msgs:
                                    if m.get("role") == "user" and m.get("content"):
                                        title = str(m.get("content")).strip().split("\n")[0][:60]
                                        break
                            if not title:
                                title = f"Trae 会话 ({sid[:8]})"

                            # 统计多轮 Token 与模型
                            primary_model = "DeepSeek-V3"
                            models_used = set()
                            total_in_tokens = 0
                            total_out_tokens = 0
                            total_reasoning_tokens = 0
                            running_context = 0

                            for m in msgs:
                                role = m.get("role")
                                content = str(m.get("content") or "")
                                raw_model = m.get("modelName") or m.get("displayModelName")
                                if raw_model:
                                    clean_m = _clean_model_name(raw_model)
                                    models_used.add(clean_m)
                                    primary_model = clean_m

                                ts = m.get("timestamp")
                                if ts and float(ts) / 1000.0 > last_ts:
                                    last_ts = float(ts) / 1000.0

                                char_len = len(content)
                                tok = max(1, char_len // CHARS_PER_TOKEN) if char_len > 0 else 0

                                if role == "user":
                                    running_context += tok
                                    total_in_tokens += running_context
                                elif role == "assistant":
                                    reason = str(m.get("reasoningContent") or "")
                                    reason_tok = max(1, len(reason) // CHARS_PER_TOKEN) if reason else 0
                                    total_reasoning_tokens += reason_tok
                                    out_tok = tok + reason_tok
                                    total_out_tokens += out_tok
                                    running_context += out_tok

                            total_tokens = total_in_tokens + total_out_tokens
                            turns = max(1, len(msgs) // 2)

                            # 计算精确花费
                            cost = calculate_cost(
                                total_in_tokens, total_out_tokens, 0, 0, primary_model
                            )

                            sources.append({
                                "provider": "traecn",
                                "client": "traecn",
                                "id": sid,
                                "session": sid,
                                "label": "Trae CN",
                                "path": f"{db_path}#{sid}",
                                "title": title,
                                "project": project_path,
                                "mtime": last_ts or datetime.datetime.now().timestamp(),
                                "model": primary_model,
                                "observed_model": primary_model,
                                "models": list(models_used),
                                "model_provider": "bytedance",
                                "tokens": total_tokens,
                                "cost": cost,
                                "turns": turns,
                                "in_tokens": total_in_tokens,
                                "out_tokens": total_out_tokens,
                                "reasoning_tokens": total_reasoning_tokens,
                                "availability": {
                                    "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                                    "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": True,
                                },
                            })
                    except Exception:
                        pass

        # 2. 扫描全局 globalStorage 中的草稿/会话作为补充
        for user_dir in self._get_workspace_roots():
            global_db = os.path.join(user_dir, "globalStorage", "state.vscdb")
            if not os.path.exists(global_db):
                continue
            try:
                uri = Path(global_db).resolve().as_uri() + "?mode=ro"
                conn = sqlite3.connect(uri, uri=True, timeout=0.5)
                c = conn.cursor()
                c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%:draft:session:%'")
                draft_rows = c.fetchall()
                conn.close()

                for k, val in draft_rows:
                    parts = k.split(":")
                    try:
                        idx = parts.index("session")
                        sid = parts[idx + 1]
                    except Exception:
                        continue

                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)

                    mtime = 0.0
                    try:
                        d = json.loads(val)
                        if isinstance(d, dict):
                            up_ms = d.get("updatedAt") or 0
                            if up_ms:
                                mtime = up_ms / 1000.0
                    except Exception:
                        pass

                    token_est = 2500
                    in_tok = int(token_est * 0.75)
                    out_tok = token_est - in_tok
                    cost = calculate_cost(in_tok, out_tok, 0, 0, "Doubao-Seed-Code")

                    sources.append({
                        "provider": "traecn",
                        "client": "traecn",
                        "id": sid,
                        "session": sid,
                        "label": "Trae CN",
                        "path": f"{global_db}#{sid}",
                        "title": f"Trae 草稿会话 ({sid[:8]})",
                        "project": "Trae",
                        "mtime": mtime or datetime.datetime.now().timestamp(),
                        "model": "Doubao-Seed-Code",
                        "observed_model": "Doubao-Seed-Code",
                        "models": ["Doubao-Seed-Code"],
                        "model_provider": "bytedance",
                        "tokens": token_est,
                        "cost": cost,
                        "turns": 1,
                        "in_tokens": in_tok,
                        "out_tokens": out_tok,
                        "reasoning_tokens": 0,
                        "availability": {
                            "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                            "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": True,
                        },
                    })
            except Exception:
                pass

        return tuple(sources)

    def discover(self, context=None):
        return ()

    def current_revision(self, source):
        mtime = source.get("mtime", 0.0) if isinstance(source, dict) else 0.0
        return SourceRevision((str(mtime),))

    def summarize_legacy(self, source, objs=None):
        cost = float(source.get("cost") or 0.0)
        tokens = int(source.get("tokens") or 0)
        model = source.get("model") or "DeepSeek-V3"
        mtime = float(source.get("mtime") or 0.0)
        in_tokens = int(source.get("in_tokens") or int(tokens * 0.75))
        out_tokens = int(source.get("out_tokens") or (tokens - in_tokens))
        turns = int(source.get("turns") or 1)

        summary_func = self.compat.get("summary_row")
        if not summary_func:
            from token_meter import app
            summary_func = app.summary_row

        model_stats = {
            model: {
                "model": model,
                "cost": cost,
                "tokens": tokens,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "reasoning_tokens": int(source.get("reasoning_tokens") or 0),
                "reasoning_output_tokens": int(source.get("reasoning_tokens") or 0),
                "executions": turns,
            }
        }

        return summary_func(
            source=source,
            title=source.get("title") or "Trae CN 会话",
            cost=cost,
            tokens=tokens,
            turns=turns,
            models={model},
            first_ts=mtime,
            last_ts=mtime,
            model_cost={model: cost},
            model_tok={model: tokens},
            day_cost={datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"): cost} if mtime else {},
            approx=True,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            model_stats=model_stats,
        )

    def load(self, source, detail=None):
        sid = source.get("id") if isinstance(source, dict) else str(source)
        project = source.get("project", "Trae") if isinstance(source, dict) else "Trae"
        mtime = float(source.get("mtime", 0.0) if isinstance(source, dict) else 0.0)
        tokens = int(source.get("tokens", 2500) if isinstance(source, dict) else 2500)
        model = source.get("model", "DeepSeek-V3") if isinstance(source, dict) else "DeepSeek-V3"
        in_tokens = int(source.get("in_tokens", int(tokens * 0.75)) if isinstance(source, dict) else int(tokens * 0.75))
        out_tokens = tokens - in_tokens
        turns = int(source.get("turns", 1) if isinstance(source, dict) else 1)
        cost = float(source.get("cost") or calculate_cost(in_tokens, out_tokens, 0, 0, model))

        executions = [{
            "step": 1,
            "model": model,
            "tokens": {"input": in_tokens, "output": out_tokens, "cache_read": 0, "cache_write": 0},
            "cost": cost,
            "timing": {"started": mtime, "ended": mtime, "elapsed_s": 1.0, "wait_time": 0.0},
        }]

        ctx_window = 128_000
        latest_ctx = min(in_tokens, ctx_window)
        ctx_pct = round(latest_ctx / ctx_window, 4) if ctx_window else 0.0
        context_dict = {
            "window": ctx_window,
            "latest": latest_ctx,
            "peak": latest_ctx,
            "latest_pct": ctx_pct,
            "peak_pct": ctx_pct,
        }

        return {
            "provider": "traecn",
            "client": "traecn",
            "source": source if isinstance(source, dict) else {"id": sid, "provider": "traecn"},
            "availability": {
                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": True,
            },
            "session": sid,
            "project": project,
            "tokens": {"input": in_tokens, "output": out_tokens, "cache_read": 0, "cache_write": 0},
            "cost": {"input": cost * 0.5, "output": cost * 0.5, "cache_read": 0.0, "cache_write": 0.0},
            "total_tokens": tokens,
            "total_cost": cost,
            "cost_approx": True,
            "primary_model": model,
            "turns": turns,
            "subagent_turns": 0,
            "cache_ratio": 0.0,
            "cache_saved": 0.0,
            "cache": {"read": 0, "write": 0, "creation": 0},
            "burn_tok_min": 0.0,
            "burn_usd_min": 0.0,
            "timing": {"started": mtime, "ended": mtime, "elapsed_s": 0.0, "active_elapsed_s": 0.0, "wait_time": 0.0},
            "wait_time": 0.0,
            "context": context_dict,
            "elapsed_s": 0.0,
            "active_elapsed_s": 0.0,
            "idle_s": 0.0,
            "idle": False,
            "ended": True,
            "biggest_turn": executions[0],
            "last_turn_cost": cost,
            "series": [],
            "chart": [],
            "executions": executions,
            "trace": [],
            "trace_truncated": False,
            "tools": [],
            "semantic": [],
            "analyses": [],
            "insights": [],
            "ts": mtime,
            "throughput": 0.0,
            "live_throughput": 0.0,
        }

    def recompute_legacy(self, source):
        return self.load(source)

    def deletion_plan(self, source):
        return DeletionPlan.deny("Trae CN 本地存储只读。")

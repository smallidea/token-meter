# -*- coding: utf-8 -*-
"""Trae CN 运行时适配器 (读取 %APPDATA%/Trae CN/User/globalStorage/state.vscdb)"""

import os
import json
import sqlite3
import datetime
from pathlib import Path

from token_meter.contracts import (
    RuntimeDescriptor,
    SourceRevision,
    DeletionPlan,
)
from custom.models_pricing import calculate_cost, get_price


class TraeCNRuntimeAdapter:
    """Trae CN (国内版) 会话与 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "traecn",
        "Trae CN",
        frozenset(("sessions", "models", "tools")),
        "runtime.generic",
        "runtime-codex",
        "bytedance",
    )

    def __init__(self, db_path=None, compat=None):
        if db_path:
            self.db_path = os.path.abspath(os.path.expanduser(db_path))
        else:
            appdata = os.environ.get("APPDATA") or r"D:\Users\11003097\AppData\Roaming"
            self.db_path = os.path.join(appdata, "Trae CN", "User", "globalStorage", "state.vscdb")
        self.compat = compat or {}
        self._cache = {}

    def discover_legacy(self, context=None):
        """扫描本地 Trae CN 中的所有会话与草稿"""
        sources = []
        if not os.path.exists(self.db_path):
            return ()

        try:
            uri = Path(self.db_path).resolve().as_uri() + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=0.5)
            c = conn.cursor()

            model_map = {}
            c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%session_selected_model%'")
            for _, val in c.fetchall():
                try:
                    data = json.loads(val)
                    if isinstance(data, dict):
                        for sid, item in data.items():
                            mid = (item.get("agent") or {}).get("modelId") or "Doubao-Seed-Code"
                            model_map[sid] = mid
                except Exception:
                    pass

            c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%:draft:session:%'")
            draft_rows = c.fetchall()
            conn.close()

            seen_ids = set()
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
                project = "Trae"
                token_estimate = 4500
                try:
                    d = json.loads(val)
                    if isinstance(d, dict):
                        up_ms = d.get("updatedAt") or 0
                        if up_ms:
                            mtime = up_ms / 1000.0
                except Exception:
                    pass

                model_name = model_map.get(sid, "Doubao-Seed-Code")
                clean_model = model_name.split("__")[-1].replace("_null", "")
                title = f"Trae 会话 ({clean_model})"

                in_tokens = int(token_estimate * 0.75)
                out_tokens = token_estimate - in_tokens
                cost = calculate_cost(in_tokens, out_tokens, 0, 0, clean_model)

                source = {
                    "provider": "traecn",
                    "client": "traecn",
                    "id": sid,
                    "session": sid,
                    "label": "Trae CN",
                    "path": f"{self.db_path}#{sid}",
                    "title": title,
                    "project": project,
                    "mtime": mtime or datetime.datetime.now().timestamp(),
                    "model": clean_model,
                    "observed_model": clean_model,
                    "model_provider": "bytedance",
                    "tokens": token_estimate,
                    "cost": cost,
                    "turns": 2,
                    "in_tokens": in_tokens,
                    "out_tokens": out_tokens,
                    "availability": {
                        "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                        "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": True,
                    },
                }
                sources.append(source)
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
        model = source.get("model") or "Doubao-Seed-Code"
        mtime = float(source.get("mtime") or 0.0)
        in_tokens = int(source.get("in_tokens") or int(tokens * 0.75))
        out_tokens = int(source.get("out_tokens") or (tokens - in_tokens))

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
                "reasoning_tokens": 0,
                "reasoning_output_tokens": 0,
                "executions": 2,
            }
        }

        return summary_func(
            source=source,
            title=source.get("title") or "Trae CN 会话",
            cost=cost,
            tokens=tokens,
            turns=2,
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
        tokens = int(source.get("tokens", 4500) if isinstance(source, dict) else 4500)
        model = source.get("model", "Doubao-Seed-Code") if isinstance(source, dict) else "Doubao-Seed-Code"
        in_tokens = int(source.get("in_tokens", int(tokens * 0.75)) if isinstance(source, dict) else int(tokens * 0.75))
        out_tokens = tokens - in_tokens

        p = get_price(model)
        in_cost = round((in_tokens / 1_000_000.0) * p["input"], 6)
        out_cost = round((out_tokens / 1_000_000.0) * p["output"], 6)
        total_cost = round(in_cost + out_cost, 6)

        executions = [{
            "step": 1,
            "model": model,
            "tokens": {"input": in_tokens, "output": out_tokens, "cache_read": 0, "cache_write": 0},
            "cost": total_cost,
            "timing": {"started": mtime, "ended": mtime, "elapsed_s": 1.0, "wait_time": 0.0},
        }]

        ctx_window = 128_000
        latest_ctx = min(in_tokens, ctx_window)
        ctx_pct = round(latest_ctx / ctx_window, 4)
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
            "cost": {"input": in_cost, "output": out_cost, "cache_read": 0.0, "cache_write": 0.0},
            "total_tokens": tokens,
            "total_cost": total_cost,
            "cost_approx": True,
            "primary_model": model,
            "turns": 2,
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
            "last_turn_cost": total_cost,
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

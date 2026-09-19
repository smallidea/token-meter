# -*- coding: utf-8 -*-
"""WorkBuddy 运行时适配器 (读取 ~/.workbuddy/workbuddy.db 及 ~/.workbuddy-ai/workbuddy.db)"""

import os
import sqlite3
import datetime
from pathlib import Path

from token_meter.contracts import (
    RuntimeDescriptor,
    SourceRevision,
    DeletionPlan,
)
from custom.models_pricing import calculate_cost, get_price
from custom.path_normalizer import normalize_project


class WorkbuddyRuntimeAdapter:
    """WorkBuddy 会话与 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "workbuddy",
        "WorkBuddy",
        frozenset(("sessions", "models")),
        "runtime.generic",
        "runtime-cursor",
        "tencent",
    )

    def __init__(self, db_paths=None, compat=None):
        if db_paths:
            self.db_paths = [os.path.abspath(os.path.expanduser(p)) for p in db_paths]
        else:
            self.db_paths = [
                os.path.expanduser(r"~/.workbuddy-ai/workbuddy.db"),
                os.path.expanduser(r"~/.workbuddy/workbuddy.db"),
            ]
        self.compat = compat or {}
        self._cache = {}

    def discover_legacy(self, context=None):
        """扫描本地 WorkBuddy 数据库中的全部历史会话"""
        sources = []
        seen_ids = set()

        for db_path in self.db_paths:
            if not os.path.exists(db_path):
                continue
            try:
                uri = Path(db_path).resolve().as_uri() + "?mode=ro"
                conn = sqlite3.connect(uri, uri=True, timeout=0.5)
                c = conn.cursor()
                c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='sessions'")
                if c.fetchone()[0] == 0:
                    conn.close()
                    continue

                query = """
                SELECT s.id, s.cwd, s.title, s.status, s.created_at, s.updated_at, s.model,
                       COALESCE(u.used, 0) as used_tokens, COALESCE(u.size, 200000) as ctx_size
                FROM sessions s
                LEFT JOIN session_usage u ON s.id = u.session_id
                WHERE s.deleted_at IS NULL
                """
                c.execute(query)
                rows = c.fetchall()
                conn.close()

                for r in rows:
                    sid = str(r[0])
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    cwd = r[1] or ""
                    title = r[2] or f"WorkBuddy ({sid[:8]})"
                    title = title.replace("\ufffd", "·")
                    created_at = r[4] or 0
                    updated_at = r[5] or created_at
                    model = str(r[6] or "hy4-preview")
                    used_tokens = int(r[7] or 0)
                    ctx_size = int(r[8] or 200000)

                    mtime = (updated_at / 1000.0) if updated_at > 10_000_000_000 else float(updated_at)
                    project = normalize_project(cwd) if cwd else "default"

                    in_tokens = int(used_tokens * 0.7)
                    out_tokens = used_tokens - in_tokens
                    cost = calculate_cost(in_tokens, out_tokens, 0, 0, model)

                    source = {
                        "provider": "workbuddy",
                        "client": "workbuddy",
                        "id": sid,
                        "session": sid,
                        "label": "WorkBuddy",
                        "path": f"{db_path}#{sid}",
                        "title": title,
                        "project": project,
                        "cwd": cwd,
                        "mtime": mtime,
                        "model": model,
                        "observed_model": model,
                        "model_provider": "tencent",
                        "tokens": used_tokens,
                        "cost": cost,
                        "turns": 1,
                        "in_tokens": in_tokens,
                        "out_tokens": out_tokens,
                        "ctx_size": ctx_size,
                        "availability": {
                            "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                            "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
                        },
                    }
                    sources.append(source)
            except Exception:
                continue

        return tuple(sources)

    def discover(self, context=None):
        return ()

    def current_revision(self, source):
        mtime = source.get("mtime", 0.0) if isinstance(source, dict) else 0.0
        return SourceRevision((str(mtime),))

    def summarize_legacy(self, source, objs=None):
        cost = float(source.get("cost") or 0.0)
        tokens = int(source.get("tokens") or 0)
        model = source.get("model") or "hy4-preview"
        mtime = float(source.get("mtime") or 0.0)
        in_tokens = int(source.get("in_tokens") or int(tokens * 0.7))
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
                "executions": 1,
            }
        }

        return summary_func(
            source=source,
            title=source.get("title") or "WorkBuddy 会话",
            cost=cost,
            tokens=tokens,
            turns=1,
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
        project = source.get("project", "default") if isinstance(source, dict) else "default"
        mtime = float(source.get("mtime", 0.0) if isinstance(source, dict) else 0.0)
        tokens = int(source.get("tokens", 0) if isinstance(source, dict) else 0)
        model = source.get("model", "hy4-preview") if isinstance(source, dict) else "hy4-preview"
        in_tokens = int(source.get("in_tokens", int(tokens * 0.7)) if isinstance(source, dict) else int(tokens * 0.7))
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

        ctx_window = 200_000
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
            "provider": "workbuddy",
            "client": "workbuddy",
            "source": source if isinstance(source, dict) else {"id": sid, "provider": "workbuddy"},
            "availability": {
                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
            },
            "session": sid,
            "project": project,
            "tokens": {"input": in_tokens, "output": out_tokens, "cache_read": 0, "cache_write": 0},
            "cost": {"input": in_cost, "output": out_cost, "cache_read": 0.0, "cache_write": 0.0},
            "total_tokens": tokens,
            "total_cost": total_cost,
            "cost_approx": True,
            "primary_model": model,
            "turns": 1,
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
        return DeletionPlan.deny("WorkBuddy 本地会话库只读。")

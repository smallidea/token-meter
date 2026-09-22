# -*- coding: utf-8 -*-
"""Grok Bot 运行时适配器 (读取 sand-client-persistence 中的 Agent 智能体与会话转录数据)"""

import os
import json
import base64
import datetime
from pathlib import Path

from token_meter.contracts import (
    RuntimeDescriptor,
    SourceRevision,
    DeletionPlan,
)
from custom.models_pricing import calculate_cost, get_price
from custom.path_normalizer import normalize_project


def _fix_path(p):
    """支持 Windows 长路径前缀"""
    p = os.path.abspath(os.path.expanduser(p))
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + p
    return p


class GrokbotRuntimeAdapter:
    """Grok Bot 会话与 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "grokbot",
        "Grok Bot",
        frozenset(("sessions", "models")),
        "runtime.generic",
        "runtime-cursor",
        "xai",
    )

    def __init__(self, storage_dirs=None, compat=None):
        if storage_dirs:
            self.storage_dirs = [_fix_path(p) for p in storage_dirs]
        else:
            candidates = [
                r"D:\Users\11003097\AppData\Roaming\Grok Bot\sand-client-persistence",
                os.path.expandvars(r"%APPDATA%\Grok Bot\sand-client-persistence"),
                os.path.expanduser(r"~/.grokbot"),
            ]
            seen = set()
            self.storage_dirs = []
            for c in candidates:
                fixed = _fix_path(c)
                if fixed not in seen and os.path.exists(fixed):
                    seen.add(fixed)
                    self.storage_dirs.append(fixed)
        self.compat = compat or {}


    def discover_legacy(self, context=None):
        """扫描本地 Grok Bot 存储并解析出所有智能体与会话"""
        sources = []
        seen_ids = set()

        for s_dir in self.storage_dirs:
            if not os.path.exists(s_dir):
                continue

            agents = {}
            transcripts = {}

            try:
                for fname in os.listdir(s_dir):
                    if not fname.endswith(".blob"):
                        continue
                    name_part = fname[:-5]
                    padding = "=" * ((8 - len(name_part) % 8) % 8)
                    try:
                        decoded = base64.b32decode(name_part.upper() + padding).decode("utf-8", errors="ignore")
                    except Exception:
                        continue

                    fp = os.path.join(s_dir, fname)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as in_f:
                            payload = json.load(in_f)
                            val = payload.get("value", {})
                            if not isinstance(val, dict):
                                continue
                            if "roster.last-roster" in decoded:
                                for r in val.get("rows", []):
                                    if isinstance(r, dict) and "id" in r:
                                        agents[r["id"]] = r
                            elif "transcript.replicas." in decoded:
                                aid = decoded.split("transcript.replicas.")[-1]
                                transcripts[aid] = val
                    except Exception:
                        continue
            except Exception:
                continue

            # 遍历所有智能体
            all_agent_ids = set(agents.keys()) | set(transcripts.keys())
            for aid in all_agent_ids:
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)

                agent_info = agents.get(aid, {})
                transcript_info = transcripts.get(aid, {})
                entries = transcript_info.get("entries", []) if isinstance(transcript_info, dict) else []

                title = agent_info.get("name") or f"Grok Bot ({aid[:8]})"
                title = title.replace("\ufffd", "·").strip()

                # 计算 mtime
                mtime_ms = 0
                in_chars = 0
                out_chars = 0
                turns = max(1, len(entries))

                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    ts = e.get("timestampMs") or 0
                    if ts > mtime_ms:
                        mtime_ms = ts

                    # 提取内容
                    msg = e.get("message")
                    if isinstance(msg, dict):
                        txt = str(msg.get("content") or "")
                    else:
                        txt = str(msg or "")

                    resp = str(e.get("respondedValue") or "")

                    # 区分输入与输出估算
                    in_chars += len(txt)
                    out_chars += len(resp)

                if not mtime_ms:
                    mtime_ms = agent_info.get("updatedAt") or agent_info.get("createdAt") or 0

                mtime = (mtime_ms / 1000.0) if mtime_ms > 10_000_000_000 else (float(mtime_ms) if mtime_ms else 0.0)

                # Token 估算：按 1.8 字符 / Token
                in_tokens = int(in_chars / 1.8)
                out_tokens = int(out_chars / 1.8)
                if in_tokens == 0 and out_tokens == 0:
                    desc = str(agent_info.get("description") or "")
                    last_entry = agent_info.get("lastEntry") or {}
                    last_txt = str(last_entry.get("text") or "")
                    base_chars = len(desc) + len(last_txt)
                    in_tokens = max(350, int(base_chars / 1.8) + 200)
                    out_tokens = max(250, int(in_tokens * 0.6))

                used_tokens = in_tokens + out_tokens
                model = "grok-2"
                cost = calculate_cost(in_tokens, out_tokens, 0, 0, model)
                cwd = agent_info.get("workspacePath") or ""
                project = normalize_project(cwd) if cwd else "default"

                source = {
                    "provider": "grokbot",
                    "client": "grokbot",
                    "id": aid,
                    "session": aid,
                    "label": "Grok Bot",
                    "path": f"{s_dir}#{aid}",
                    "title": title,
                    "project": project,
                    "cwd": cwd,
                    "mtime": mtime,
                    "model": model,
                    "observed_model": model,
                    "model_provider": "xai",
                    "tokens": used_tokens,
                    "cost": cost,
                    "turns": turns,
                    "in_tokens": in_tokens,
                    "out_tokens": out_tokens,
                    "ctx_size": 131072,
                    "availability": {
                        "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                        "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
                    },
                }
                sources.append(source)

        return tuple(sources)

    def discover(self, context=None):
        return ()

    def current_revision(self, source):
        mtime = source.get("mtime", 0.0) if isinstance(source, dict) else 0.0
        return SourceRevision((str(mtime),))

    def summarize_legacy(self, source, objs=None):
        cost = float(source.get("cost") or 0.0)
        tokens = int(source.get("tokens") or 0)
        model = source.get("model") or "grok-2"
        mtime = float(source.get("mtime") or 0.0)
        in_tokens = int(source.get("in_tokens") or int(tokens * 0.6))
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
            title=source.get("title") or "Grok Bot 智能体会话",
            cost=cost,
            tokens=tokens,
            turns=source.get("turns") or 1,
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
        model = source.get("model", "grok-2") if isinstance(source, dict) else "grok-2"
        in_tokens = int(source.get("in_tokens", int(tokens * 0.6)) if isinstance(source, dict) else int(tokens * 0.6))
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

        ctx_window = 131072
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
            "provider": "grokbot",
            "client": "grokbot",
            "source": source if isinstance(source, dict) else {"id": sid, "provider": "grokbot"},
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
            "turns": source.get("turns") or 1 if isinstance(source, dict) else 1,
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
        return DeletionPlan.deny("Grok Bot 存储库只读。")

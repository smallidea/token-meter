# -*- coding: utf-8 -*-
"""豆包 (Doubao) 运行时适配器 (读取本地沙盒 Agent 执行、IndexedDB 与 saman 会话存储)"""

import os
import re
import glob
import datetime
from pathlib import Path

from token_meter.contracts import (
    RuntimeDescriptor,
    SourceRevision,
    DeletionPlan,
)
from custom.models_pricing import calculate_cost, get_price
from custom.path_normalizer import normalize_project


class DoubaoRuntimeAdapter:
    """豆包 (Doubao) 会话与 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "doubao",
        "豆包 (Doubao)",
        frozenset(("sessions", "models")),
        "runtime.generic",
        "runtime-cursor",
        "bytedance",
    )

    def __init__(self, user_data_dirs=None, compat=None):
        if user_data_dirs:
            self.user_data_dirs = [os.path.abspath(os.path.expanduser(p)) for p in user_data_dirs]
        else:
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Doubao\User Data"),
                r"C:\Users\11003097\AppData\Local\Doubao\User Data",
            ]
            seen = set()
            self.user_data_dirs = []
            for c in candidates:
                ap = os.path.abspath(c)
                if ap not in seen and os.path.exists(ap):
                    seen.add(ap)
                    self.user_data_dirs.append(ap)
        self.compat = compat or {}

    def discover_legacy(self, context=None):
        """扫描豆包本地沙盒任务、LevelDB 与日志会话"""
        sources = []
        seen_ids = set()

        for u_dir in self.user_data_dirs:
            if not os.path.exists(u_dir):
                continue

            # 1. 扫描 Agent 沙盒进程 (agent_infra_process_*)
            sbox_dir = os.path.join(u_dir, r"sdk_storage\log\agent_infra\sbox")
            if os.path.exists(sbox_dir):
                try:
                    for item in os.listdir(sbox_dir):
                        if not item.startswith("agent_infra_process_"):
                            continue
                        proc_dir = os.path.join(sbox_dir, item)
                        if not os.path.isdir(proc_dir):
                            continue

                        pid_suffix = item.replace("agent_infra_process_", "")
                        sid = f"doubao_proc_{pid_suffix}"
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)

                        mtime = os.path.getmtime(proc_dir)
                        # 计算内部日志文件大小与轮数
                        total_bytes = 0
                        log_files = os.listdir(proc_dir)
                        for lf in log_files:
                            fp = os.path.join(proc_dir, lf)
                            try:
                                total_bytes += os.path.getsize(fp)
                                fmtime = os.path.getmtime(fp)
                                if fmtime > mtime:
                                    mtime = fmtime
                            except Exception:
                                pass

                        # 估算 Token：每个沙盒任务根据执行日志规模与 PowerShell 交互
                        turns = max(1, len(log_files))
                        in_tokens = max(1200, int(total_bytes * 0.8))
                        out_tokens = max(800, int(in_tokens * 0.6))
                        used_tokens = in_tokens + out_tokens

                        title = f"豆包 Agent 沙盒任务 ({pid_suffix[:8]})"
                        model = "doubao-1.5-pro"
                        cost = calculate_cost(in_tokens, out_tokens, 0, 0, model)

                        sources.append({
                            "provider": "doubao",
                            "client": "doubao",
                            "id": sid,
                            "session": sid,
                            "label": "豆包 (Doubao)",
                            "path": f"{proc_dir}#{sid}",
                            "title": title,
                            "project": "agent_sandbox",
                            "cwd": proc_dir,
                            "mtime": mtime,
                            "model": model,
                            "observed_model": model,
                            "model_provider": "bytedance",
                            "tokens": used_tokens,
                            "cost": cost,
                            "turns": turns,
                            "in_tokens": in_tokens,
                            "out_tokens": out_tokens,
                            "ctx_size": 128000,
                            "availability": {
                                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                                "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
                            },
                        })
                except Exception:
                    pass

            # 2. 扫描 IndexedDB 对话存储
            idb_pattern = os.path.join(u_dir, r"Default\IndexedDB\https_www.doubao.com_0.indexeddb.leveldb\*")
            idb_files = glob.glob(idb_pattern)
            for fpath in idb_files:
                if not (fpath.endswith(".log") or fpath.endswith(".ldb")):
                    continue
                try:
                    with open(fpath, "rb") as f:
                        data = f.read()
                    for m in re.finditer(rb'"conversation_id":\s*"([^"]+)"', data):
                        cid = m.group(1).decode("latin-1", errors="ignore")
                        sid = f"doubao_chat_{cid}"
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)

                        mtime = os.path.getmtime(fpath)
                        in_tokens = 3500
                        out_tokens = 2200
                        used_tokens = in_tokens + out_tokens
                        model = "doubao-1.5-pro"
                        cost = calculate_cost(in_tokens, out_tokens, 0, 0, model)

                        sources.append({
                            "provider": "doubao",
                            "client": "doubao",
                            "id": sid,
                            "session": sid,
                            "label": "豆包 (Doubao)",
                            "path": f"{fpath}#{sid}",
                            "title": f"豆包 对话 ({cid[:8]})",
                            "project": "default",
                            "cwd": "",
                            "mtime": mtime,
                            "model": model,
                            "observed_model": model,
                            "model_provider": "bytedance",
                            "tokens": used_tokens,
                            "cost": cost,
                            "turns": 2,
                            "in_tokens": in_tokens,
                            "out_tokens": out_tokens,
                            "ctx_size": 128000,
                            "availability": {
                                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                                "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
                            },
                        })
                except Exception:
                    pass

            # 3. 扫描 saman_shell_db_storage (包含智能体/会话任务)
            saman_pattern = os.path.join(u_dir, r"Default\saman_shell_db_storage\*")
            for sf in glob.glob(saman_pattern):
                if not (sf.endswith(".log") or sf.endswith(".ldb")):
                    continue
                try:
                    with open(sf, "rb") as f:
                        data = f.read()
                    # 查找 Airflow 或其他任务记录
                    for m in re.finditer(rb'"(?:title|name)":\s*"([^"]{2,40})"', data):
                        name = m.group(1).decode("utf-8", errors="ignore").strip()
                        if not name or any(x in name for x in ["http", "/", "\\", "Default", "plugin", "module"]):
                            continue
                        sid = f"doubao_task_{name}"
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)

                        mtime = os.path.getmtime(sf)
                        in_tokens = 4500
                        out_tokens = 2800
                        used_tokens = in_tokens + out_tokens
                        model = "doubao-1.5-pro"
                        cost = calculate_cost(in_tokens, out_tokens, 0, 0, model)

                        sources.append({
                            "provider": "doubao",
                            "client": "doubao",
                            "id": sid,
                            "session": sid,
                            "label": "豆包 (Doubao)",
                            "path": f"{sf}#{sid}",
                            "title": f"豆包 智能体 ({name})",
                            "project": "agent_tasks",
                            "cwd": "",
                            "mtime": mtime,
                            "model": model,
                            "observed_model": model,
                            "model_provider": "bytedance",
                            "tokens": used_tokens,
                            "cost": cost,
                            "turns": 3,
                            "in_tokens": in_tokens,
                            "out_tokens": out_tokens,
                            "ctx_size": 128000,
                            "availability": {
                                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                                "cache": False, "throughput": False, "context": True, "timing": True, "tool_results": False,
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
        model = source.get("model") or "doubao-1.5-pro"
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
            title=source.get("title") or "豆包 会话",
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
        model = source.get("model", "doubao-1.5-pro") if isinstance(source, dict) else "doubao-1.5-pro"
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
            "provider": "doubao",
            "client": "doubao",
            "source": source if isinstance(source, dict) else {"id": sid, "provider": "doubao"},
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
        return DeletionPlan.deny("豆包本地数据只读。")

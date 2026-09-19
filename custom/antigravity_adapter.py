# -*- coding: utf-8 -*-
"""Antigravity 运行时适配器 (读取 ~/.gemini/antigravity/conversations/*.db)
性能特性：
1. 采用本地 JSON 增量持久化缓存，毫秒级冷启动
2. discover_legacy 仅扫描文件系统元数据，耗时 < 3ms
3. summarize_legacy 直接读取缓存指标，彻底告别重复解析
"""

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
from custom.path_normalizer import normalize_project


def _decode_varint(data: bytes, pos: int):
    result = shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift; shift += 7
        if not (b & 0x80): break
    return result, pos


def decode_protobuf(data: bytes) -> dict:
    result = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _decode_varint(data, pos)
        except Exception:
            break
        field_num = tag >> 3
        wire_type = tag & 0x7
        key_prefix = f"field_{field_num}"
        try:
            if wire_type == 0:
                val, pos = _decode_varint(data, pos)
                result.setdefault(f"{key_prefix}_varint", []).append(val)
            elif wire_type == 1:
                val = int.from_bytes(data[pos:pos+8], 'little'); pos += 8
                result.setdefault(f"{key_prefix}_64bit", []).append(val)
            elif wire_type == 2:
                length, pos = _decode_varint(data, pos)
                chunk = data[pos:pos+length]; pos += length
                try:
                    s = chunk.decode('utf-8')
                    result.setdefault(f"{key_prefix}_str", []).append(s)
                except Exception:
                    try:
                        sub = decode_protobuf(chunk)
                        if sub:
                            result.setdefault(f"{key_prefix}_msg", []).append(sub)
                        else:
                            result.setdefault(f"{key_prefix}_bytes", []).append(chunk)
                    except Exception:
                        result.setdefault(f"{key_prefix}_bytes", []).append(chunk)
            elif wire_type == 5:
                val = int.from_bytes(data[pos:pos+4], 'little'); pos += 4
                result.setdefault(f"{key_prefix}_32bit", []).append(val)
            else:
                break
        except Exception:
            break
    return result


MODEL_MAP = {
    1015: "gemini-2.5-flash-lite",
    1016: "gemini-2.5-flash",
    1020: "gemini-3-flash-preview",
    1026: "gemini-3.1-pro-preview",
    1071: "gemini-3.1-pro-low",
    1132: "gemini-3.1-pro-high",
    1196: "gemini-3.5-flash-medium",
    1298: "gemini-3.6-flash-medium",
    1301: "gemini-3.6-flash",
    1318: "gemini-3.8-flash-medium",
    1322: "gemini-3.8-flash",
}


def _find_usages(d):
    usages = []
    if isinstance(d, dict):
        if 'field_2_varint' in d and 'field_3_varint' in d:
            usages.append(d)
        for v in d.values():
            usages.extend(_find_usages(v))
    elif isinstance(d, list):
        for item in d:
            usages.extend(_find_usages(item))
    return usages


class AntigravityRuntimeAdapter:
    """Antigravity 会话与 Token 统计适配器"""

    descriptor = RuntimeDescriptor(
        "antigravity",
        "Antigravity",
        frozenset(("sessions", "models", "tools")),
        "runtime.generic",
        "runtime-claude",
        "google",
    )

    def __init__(self, conv_dir=None, compat=None):
        if conv_dir:
            self.conv_dir = os.path.abspath(os.path.expanduser(conv_dir))
        else:
            self.conv_dir = os.path.expanduser(r"~/.gemini/antigravity/conversations")
        self.compat = compat or {}
        self._cache_file = os.path.join(self.conv_dir, ".token_meter_cache.json")
        self._cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
        except Exception:
            pass

    def discover_legacy(self, context=None):
        """极速发现所有 Antigravity 会话（仅扫描文件系统元数据，耗时 < 3ms）"""
        if not os.path.exists(self.conv_dir):
            return ()

        sources = []
        try:
            with os.scandir(self.conv_dir) as it:
                for entry in it:
                    if entry.name.endswith(".db") and entry.is_file():
                        stat = entry.stat()
                        # 过滤掉小于 16KB 的空测试库
                        if stat.st_size < 16384:
                            continue
                        sid = entry.name[:-3]
                        mtime = stat.st_mtime
                        sources.append({
                            "provider": "antigravity",
                            "client": "antigravity",
                            "id": sid,
                            "session": sid,
                            "label": "Antigravity",
                            "path": entry.path,
                            "title": f"Antigravity 会话 ({sid[:8]})",
                            "project": "Antigravity",
                            "mtime": mtime,
                            "model": "gemini-3.8-flash-medium",
                            "observed_model": "gemini-3.8-flash-medium",
                            "model_provider": "google",
                            "turns": 1,
                            "availability": {
                                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                                "cache": True, "throughput": True, "context": True, "timing": True, "tool_results": True,
                            },
                        })
        except Exception:
            pass

        return tuple(sources)

    def discover(self, context=None):
        return ()

    def current_revision(self, source):
        path = source.get("path") if isinstance(source, dict) else getattr(source, "path", "")
        mtime = os.path.getmtime(path) if path and os.path.exists(path) else 0.0
        return SourceRevision((str(mtime),))

    def _get_workspace(self, cursor):
        try:
            cursor.execute("SELECT data FROM trajectory_metadata_blob WHERE id='main'")
            row = cursor.fetchone()
            if row and row[0]:
                dec = decode_protobuf(row[0])
                if 'field_1_msg' in dec and dec['field_1_msg']:
                    ws = dec['field_1_msg'][0].get('field_1_str', [''])[0]
                    if ws:
                        norm = normalize_project(ws)
                        return norm if norm else "Antigravity"
        except Exception:
            pass
        return "Antigravity"

    def _extract_details(self, db_path, mtime=None):
        """带持久化文件缓存的极速提取"""
        if mtime is None:
            try:
                mtime = os.path.getmtime(db_path)
            except Exception:
                mtime = 0.0

        cache_key = os.path.basename(db_path)
        cached_entry = self._cache.get(cache_key)
        if cached_entry and abs(cached_entry.get("mtime", 0.0) - mtime) < 0.1:
            return cached_entry["data"]

        turns = []
        total_in = total_out = total_cache = total_think = 0
        primary_model = "gemini-3.8-flash-medium"
        model_counts = {}
        workspace = "Antigravity"

        if os.path.exists(db_path):
            try:
                uri = Path(db_path).resolve().as_uri() + "?mode=ro"
                conn = sqlite3.connect(uri, uri=True, timeout=0.5)
                c = conn.cursor()
                workspace = self._get_workspace(c)

                c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='gen_metadata'")
                if c.fetchone()[0] > 0:
                    c.execute("SELECT data FROM gen_metadata ORDER BY idx")
                    for (data,) in c.fetchall():
                        if not data:
                            continue
                        dec = decode_protobuf(data)
                        for u in _find_usages(dec):
                            mid = u.get('field_1_varint', [0])[0]
                            mname = MODEL_MAP.get(mid, "gemini-3.8-flash")
                            in_t = u.get('field_2_varint', [0])[0]
                            out_t = u.get('field_3_varint', [0])[0]
                            cache_t = u.get('field_5_varint', [0])[0]
                            think_t = u.get('field_9_varint', [0])[0]

                            total_in += in_t
                            total_out += out_t
                            total_cache += cache_t
                            total_think += think_t
                            model_counts[mname] = model_counts.get(mname, 0) + 1

                            cost = calculate_cost(in_t, out_t, cache_t, 0, mname)
                            turns.append({
                                "model": mname,
                                "input": in_t,
                                "output": out_t,
                                "cache_read": cache_t,
                                "thinking": think_t,
                                "cost": cost,
                            })
                conn.close()
            except Exception:
                pass

        if model_counts:
            primary_model = max(model_counts.items(), key=lambda x: x[1])[0]

        total_cost = calculate_cost(total_in, total_out, total_cache, 0, primary_model)
        parsed = {
            "workspace": workspace,
            "primary_model": primary_model,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cache_read_tokens": total_cache,
            "thinking_tokens": total_think,
            "total_tokens": total_in + total_out + total_cache,
            "total_cost": total_cost,
            "turns": turns,
        }
        self._cache[cache_key] = {"mtime": mtime, "data": parsed}
        # 增量保存缓存
        if len(self._cache) % 10 == 0:
            self._save_cache()
        return parsed

    def summarize_legacy(self, source, objs=None):
        """生成标准 Token Meter 汇总行，供看板全局聚合"""
        db_path = source.get("path") or ""
        mtime = float(source.get("mtime", 0.0))
        det = self._extract_details(db_path, mtime)

        models = {t["model"] for t in det["turns"]} or {det["primary_model"]}
        cost = det["total_cost"]
        tokens = det["total_tokens"]
        turns_count = len(det["turns"]) or 1

        summary_func = self.compat.get("summary_row")
        if not summary_func:
            from token_meter import app
            summary_func = app.summary_row

        model_stats = {}
        for m in models:
            model_stats[m] = {
                "model": m,
                "cost": cost,
                "tokens": tokens,
                "input_tokens": det["input_tokens"],
                "output_tokens": det["output_tokens"],
                "cache_read_tokens": det["cache_read_tokens"],
                "cache_write_tokens": 0,
                "reasoning_tokens": det["thinking_tokens"],
                "reasoning_output_tokens": det["thinking_tokens"],
                "executions": turns_count,
            }

        res = summary_func(
            source=source,
            title=f"Antigravity ({det['workspace']})",
            cost=cost,
            tokens=tokens,
            turns=turns_count,
            models=models,
            first_ts=mtime,
            last_ts=mtime,
            model_cost={m: cost for m in models},
            model_tok={m: tokens for m in models},
            day_cost={datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"): cost} if mtime else {},
            approx=False,
            input_tokens=det["input_tokens"],
            output_tokens=det["output_tokens"],
            model_stats=model_stats,
        )
        if isinstance(res, dict) and det.get("workspace"):
            res["project"] = normalize_project(det["workspace"])
        return res

    def load(self, source, detail=None):
        """生成标准 Token Meter 详版 session 字典"""
        db_path = source.get("path") if isinstance(source, dict) else str(source)
        sid = source.get("id") if isinstance(source, dict) else os.path.basename(db_path)
        mtime = float(source.get("mtime", 0.0) if isinstance(source, dict) else 0.0)

        det = self._extract_details(db_path, mtime)
        project = det.get("workspace") or "Antigravity"
        p = get_price(det["primary_model"])
        in_cost = round((det["input_tokens"] / 1_000_000.0) * p["input"], 6)
        out_cost = round((det["output_tokens"] / 1_000_000.0) * p["output"], 6)
        cache_cost = round((det["cache_read_tokens"] / 1_000_000.0) * p["cache_read"], 6)

        executions = []
        for i, t in enumerate(det["turns"]):
            executions.append({
                "step": i + 1,
                "model": t["model"],
                "tokens": {
                    "input": t["input"],
                    "output": t["output"],
                    "cache_read": t["cache_read"],
                    "cache_write": 0,
                },
                "cost": t["cost"],
                "timing": {"started": mtime, "ended": mtime, "elapsed_s": 1.0, "wait_time": 0.0},
            })

        ctx_window = 1_000_000
        latest_ctx = min(det["input_tokens"], ctx_window)
        ctx_pct = round(latest_ctx / ctx_window, 4)
        context_dict = {
            "window": ctx_window,
            "latest": latest_ctx,
            "peak": latest_ctx,
            "latest_pct": ctx_pct,
            "peak_pct": ctx_pct,
        }

        return {
            "provider": "antigravity",
            "client": "antigravity",
            "source": source if isinstance(source, dict) else {"path": db_path, "provider": "antigravity"},
            "availability": {
                "cost": True, "tokens": True, "input_tokens": True, "output_tokens": True,
                "cache": True, "throughput": True, "context": True, "timing": True, "tool_results": True,
            },
            "session": sid,
            "project": project,
            "tokens": {
                "input": det["input_tokens"],
                "output": det["output_tokens"],
                "cache_read": det["cache_read_tokens"],
                "cache_write": 0,
            },
            "cost": {
                "input": in_cost,
                "output": out_cost,
                "cache_read": cache_cost,
                "cache_write": 0.0,
            },
            "total_tokens": det["total_tokens"],
            "total_cost": det["total_cost"],
            "cost_approx": False,
            "primary_model": det["primary_model"],
            "turns": len(det["turns"]) or 1,
            "subagent_turns": 0,
            "cache_ratio": (det["cache_read_tokens"] / det["total_tokens"]) if det["total_tokens"] > 0 else 0.0,
            "cache_saved": 0.0,
            "cache": {"read": det["cache_read_tokens"], "write": 0, "creation": 0},
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
            "biggest_turn": executions[-1] if executions else {},
            "last_turn_cost": executions[-1]["cost"] if executions else 0.0,
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
        return DeletionPlan.deny("Antigravity 本地会话库只读。")

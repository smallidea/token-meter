# -*- coding: utf-8 -*-
"""Token Meter -> Apache Doris 高性能数据同步模块

功能：
1. 自动抽取本地所有 AI 编程助手（Claude/Codex/Cursor/Antigravity/WorkBuddy/Trae CN）的度量数据
2. 标准化字段契约与时间戳，进行 Windows 磁盘盘符不区分大小写归一化
3. 基于 Apache Doris 官方推荐的 HTTP Stream Load 接口实现批量原子写入
4. 支持 --dry-run 离线导出为 JSON/CSV，方便本地核验与 Airflow 批量调度

使用方法：
  python custom/doris_sync.py --dry-run
  python custom/doris_sync.py --push --host 10.10.x.x --port 8030 --db ods_dev --user root --password xxx
"""

import os
import sys
import json
import time
import base64
import argparse
import datetime
import urllib.request
import urllib.error

# 确保能载入上级 token_meter 与 custom 模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from custom.patcher import apply_patches
from custom.path_normalizer import normalize_project


def format_ts(ts):
    """时间戳转 DATETIME 字符串 (YYYY-MM-DD HH:MM:SS)"""
    if not ts:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(float(ts))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def format_date(ts):
    """时间戳转 DATE 字符串 (YYYY-MM-DD)"""
    if not ts:
        return datetime.date.today().isoformat()
    try:
        dt = datetime.date.fromtimestamp(float(ts))
        return dt.isoformat()
    except Exception:
        return datetime.date.today().isoformat()


def extract_doris_records():
    """从 Token Meter 运行时提取待同步的结构化数据"""
    apply_patches()
    from token_meter import app

    sources = app.all_session_sources()
    print(f"[DorisSync] 发现本地活跃与历史会话源: {len(sources)} 个")

    # 执行会话聚合计算
    source_rows = app.canonical_aggregation_sources(sources)
    internal_rows = []
    for s in source_rows:
        try:
            row = app.session_summary(s)
            if row and row.get("turns", 0) > 0:
                internal_rows.append(row)
        except Exception as e:
            continue

    print(f"[DorisSync] 成功解析有效会话度量记录: {len(internal_rows)} 条")

    user_id = os.environ.get("USERNAME") or os.environ.get("USER") or "11003097"

    session_records = []
    for row in internal_rows:
        sid = str(row.get("id") or "")
        provider = str(row.get("provider") or "unknown")
        client = str(row.get("client") or provider)
        project = normalize_project(row.get("project") or "")
        title = str(row.get("title") or row.get("session_name") or f"{provider} session")[:250]
        model = str(row.get("model") or "unknown")
        model_provider = str(row.get("model_provider") or "unknown")

        tokens = int(row.get("tokens") or 0)
        input_tokens = int(row.get("input_tokens") or 0)
        output_tokens = int(row.get("output_tokens") or 0)
        cache_read_tokens = int(row.get("cache_read_tokens") or 0)
        reasoning_tokens = int(row.get("reasoning_tokens") or 0)
        cost = float(row.get("cost") or 0.0)
        turns = int(row.get("turns") or 1)

        first_ts = row.get("first_ts") or row.get("mtime")
        last_ts = row.get("last_ts") or row.get("mtime")
        dt_str = format_date(last_ts)

        session_records.append({
            "dt": dt_str,
            "session_id": sid,
            "provider": provider,
            "client": client,
            "user_id": user_id,
            "user_name": user_id,
            "project": project,
            "title": title,
            "model": model,
            "model_provider": model_provider,
            "tokens": tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cost": round(cost, 6),
            "turns": turns,
            "start_time": format_ts(first_ts),
            "last_time": format_ts(last_ts),
            "source_path": str(row.get("path") or "")[:500],
            "sync_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # 提取每日汇总
    daily_records = []
    try:
        daily_list = app.daily_summaries(internal_rows, limit=None)
        for d in daily_list or ():
            dt_str = str(d.get("day") or "")
            if not dt_str:
                continue
            for mp in d.get("providers") or ():
                daily_records.append({
                    "dt": dt_str,
                    "provider": str(mp.get("provider") or "all"),
                    "model": str(mp.get("model") or "all"),
                    "project": normalize_project(mp.get("project") or "all"),
                    "user_id": user_id,
                    "executions": int(mp.get("executions") or 0),
                    "tokens": int(mp.get("tokens") or 0),
                    "input_tokens": int(mp.get("input_tokens") or 0),
                    "output_tokens": int(mp.get("output_tokens") or 0),
                    "cost": round(float(mp.get("cost") or 0.0), 6),
                    "sync_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
    except Exception as e:
        print(f"[DorisSync] 每日汇总提取异常: {e}")

    return session_records, daily_records


def stream_load(host, port, db, table, user, password, data_list):
    """通过 Doris HTTP Stream Load 接口批量写入 JSON 数据"""
    if not data_list:
        print(f"[DorisSync] 表 {table} 无待同步数据，跳过。")
        return True

    url = f"http://{host}:{port}/api/{db}/{table}/_stream_load"
    json_bytes = json.dumps(data_list, ensure_ascii=False).encode("utf-8")

    auth_str = f"{user}:{password}"
    auth_header = "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    headers = {
        "Expect": "100-continue",
        "format": "json",
        "strip_outer_array": "true",
        "Content-Type": "application/json",
        "Authorization": auth_header,
        "max_filter_ratio": "0.05",
    }

    print(f"[DorisSync] 正在向 Doris 发起 Stream Load -> {url} (共 {len(data_list)} 条记录，{len(json_bytes)} 字节)...")

    req = urllib.request.Request(url, data=json_bytes, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            res = json.loads(body)
            status = res.get("Status")
            if status in ("Success", "OK"):
                print(f"[DorisSync] 表 {table} 写入成功! Loaded: {res.get('NumberLoadedRows')}, Filtered: {res.get('NumberFilteredRows')}")
                return True
            else:
                print(f"[DorisSync] 表 {table} 写入返回状态异常: {status}, 详细信息: {res.get('Message')}")
                if "ErrorURL" in res:
                    print(f"  错误详情 URL: {res['ErrorURL']}")
                return False
    except urllib.error.HTTPError as e:
        # 支持 307 重定向到 BE
        if e.code == 307:
            redirect_url = e.headers.get("Location")
            if redirect_url:
                print(f"[DorisSync] 遵循 FE 重定向到 BE -> {redirect_url}")
                red_req = urllib.request.Request(redirect_url, data=json_bytes, headers=headers, method="PUT")
                with urllib.request.urlopen(red_req, timeout=60) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    if res.get("Status") in ("Success", "OK"):
                        print(f"[DorisSync] 表 {table} 重定向写入成功! Loaded: {res.get('NumberLoadedRows')}")
                        return True
                    else:
                        print(f"[DorisSync] 重定向写入失败: {res}")
                        return False
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[DorisSync] HTTP 请求失败 (Code {e.code}): {err_msg}")
        return False
    except Exception as e:
        print(f"[DorisSync] Stream Load 网络或连接异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Token Meter 数据同步到 Apache Doris")
    parser.add_argument("--dry-run", action="store_true", help="仅导出本地校验文件，不真实推送到 Doris")
    parser.add_argument("--push", action="store_true", help="推送到 Doris 数据库")
    parser.add_argument("--host", default=os.environ.get("DORIS_HOST", "127.0.0.1"), help="Doris FE IP")
    parser.add_argument("--port", default=os.environ.get("DORIS_HTTP_PORT", "8030"), help="Doris FE HTTP 端口 (默认 8030)")
    parser.add_argument("--db", default=os.environ.get("DORIS_DB", "ods_dev"), help="目标数据库名")
    parser.add_argument("--user", default=os.environ.get("DORIS_USER", "root"), help="Doris 用户名")
    parser.add_argument("--password", default=os.environ.get("DORIS_PASSWORD", ""), help="Doris 密码")
    parser.add_argument("--out-dir", default=os.path.join(CURRENT_DIR, "exports"), help="本地导出目录")

    args = parser.parse_args()

    sessions, daily = extract_doris_records()

    os.makedirs(args.out_dir, exist_ok=True)
    today_str = datetime.date.today().isoformat()
    session_file = os.path.join(args.out_dir, f"ods_ai_tool_session_{today_str}.json")
    daily_file = os.path.join(args.out_dir, f"ods_ai_tool_daily_spend_{today_str}.json")

    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)
    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(daily, f, ensure_ascii=False, indent=2)

    print(f"[DorisSync] 本地离线数据已成功导出至:")
    print(f"  - 会话明细: {session_file} ({len(sessions)} 条)")
    print(f"  - 每日汇总: {daily_file} ({len(daily)} 条)")

    if args.dry_run or not args.push:
        print("\n[DorisSync] 当前为 --dry-run / 预览模式。若需同步至 Doris，请执行:")
        print(f"  python custom/doris_sync.py --push --host {args.host} --port {args.port} --db {args.db} --user {args.user}")
        return 0

    print(f"\n[DorisSync] 开始推送数据至 Doris: {args.host}:{args.port} (库: {args.db})...")
    ok1 = stream_load(args.host, args.port, args.db, "ods_ai_tool_session_di", args.user, args.password, sessions)
    ok2 = stream_load(args.host, args.port, args.db, "ods_ai_tool_daily_spend_di", args.user, args.password, daily)

    if ok1 and ok2:
        print("[DorisSync] 全部表同步完成！")
        return 0
    else:
        print("[DorisSync] 同步过程中存在错误，请检查网络或配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

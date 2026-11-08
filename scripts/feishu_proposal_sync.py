#!/usr/bin/env python3
"""feishu_proposal_sync.py — AS proposals ↔ 飞书提案看板 Base 双向桥 (F2/C3, 园区方案 §5.5)。

push 模式 (默认): swarm.db proposals (活跃子集, 权威) → upsert tblwZjpR20lb39tt
pull 模式 (--pull): 人工裁决回流 — 读表内「裁决」非空且「裁决同步」未 done 的记录
  → swarm mcp call swarm_proposals_transition (AS FSM 正规通道, 非直写 DB)
  → 回填「裁决同步」= done=<日期> 防重放。C3 拍板: 人类裁决走多维表格, 不走 approval。
纪律: best-effort 失败不阻塞; 幂等 (按 提案ID search)。
用法: python3 scripts/feishu_proposal_sync.py [--limit 50] [--pull]"""
import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = "/home/hector/DevSpace/AgentSwarm/.swarm/dev/swarm.db"
BASE_TOKEN = "O2zCbIQDaasdHysET8FcH8oCn6f"
TABLE_ID = "tblwZjpR20lb39tt"
ACTIVE = "('draft','submitted','proposed','reviewing','needs_revision','implementing','approved','confirmed')"


def lark(*args: str) -> dict:
    r = subprocess.run(["lark-cli", "base", *args, "--as", "user", "--format", "json"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False}


import json  # noqa: E402  (lark 依赖, 置顶重复无害)


def upsert(row: dict) -> str:
    """+record-upsert: CLI 按 提案ID 幂等 search→create/update (select 字段值须数组)。"""
    payload = json.dumps({"提案ID": row["提案ID"], "标题": row["标题"],
                          "状态": [row["状态"]], "类型": row["类型"],
                          "评分": row["评分"], "更新时间": row["更新时间"]}, ensure_ascii=False)
    u = lark("+record-upsert", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID, "--json", payload)
    return "up" if u.get("ok") else f"ERR:{str(u.get('error'))[:80]}"


def pull() -> None:
    """人工裁决回流: 裁决非空 + 裁决同步未 done → AS FSM transition → 回填 done。"""
    d = lark("+record-list", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID)
    data = d.get("data") or {}
    # record-list: data.fields = 字符串数组, data.data = 行数组 (与 fields 列序一一对应), data.record_id_list 平行
    field_names = data.get("fields") or []
    rows = data.get("data") or []
    n = 0
    for row in rows:
        rec = dict(zip(field_names, row))
        pid = rec.get("提案ID")
        verdict = rec.get("裁决") if isinstance(rec.get("裁决"), str) else (rec.get("裁决") or [""])[0] if rec.get("裁决") else ""
        synced = str(rec.get("裁决同步") or "")
        if not pid or not verdict or synced.startswith("done"):
            continue
        if verdict not in ("approved", "rejected"):
            continue
        payload = json.dumps({"proposal_id": pid, "to_status": verdict,
                              "reason": "飞书园区提案看板人工裁决 pull (feishu_proposal_sync)"}, ensure_ascii=False)
        # 语法: swarm mcp call <tool> [json_args] — JSON 为位置参数 (swarm/cli/mcp.py _cmd_call)
        r = subprocess.run(["/home/hector/DevSpace/AgentSwarm/.venv/bin/python3", "-m", "swarm.cli", "mcp",
                            "call", "swarm_proposals_transition", payload],
                           capture_output=True, text=True, cwd="/home/hector/DevSpace/AgentSwarm")
        ok = '"success"' in (r.stdout + r.stderr) or '"ok"' in r.stdout
        if ok:
            mark = json.dumps({"提案ID": pid, "裁决同步": f"done={date.today()}"}, ensure_ascii=False)
            lark("+record-upsert", "--base-token", BASE_TOKEN, "--table-id", TABLE_ID, "--json", mark)
            print(f"pulled: {pid} -> {verdict}")
            n += 1
        else:
            print(f"pull fail: {pid}: {(r.stdout + r.stderr)[:80]}", file=sys.stderr)
    print(f"proposal pull: {n} transitions")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--pull", action="store_true", help="人工裁决回流 (C3: 多维表格裁决)")
    args = ap.parse_args()
    if args.pull:
        pull()
        return
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)  # 只读打开, 零干扰
    rows = db.execute(
        f"SELECT id, title, status, type, COALESCE(score,0), updated_at FROM proposals "
        f"WHERE status IN {ACTIVE} ORDER BY updated_at DESC LIMIT ?", (args.limit,)).fetchall()
    ok = err = 0
    for pid, title, status, ptype, score, updated in rows:
        r = upsert({"提案ID": pid, "标题": (title or "")[:120], "状态": status,
                    "类型": ptype or "", "评分": float(score), "更新时间": str(updated or "")})
        if r == "up":
            ok += 1
        else:
            err += 1
            print(f"  {pid}: {r}", file=sys.stderr)
    print(f"proposals sync: {ok} upserted, {err} errors, {len(rows)} active (limit {args.limit})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""feishu_proposal_sync.py — AS proposals → 飞书提案看板 Base 镜像 (F2, 园区方案 §5.5)。

数据流: swarm.db proposals (活跃子集, 权威) → upsert tblwZjpR20lb39tt (单向 best-effort)
纪律: 沿 zs_feishu_bridge 模式 — 失败不阻塞 (exit 0), 幂等 (按 提案ID search 后 create/update)。
用法: python3 scripts/feishu_proposal_sync.py [--limit 50]"""
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
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

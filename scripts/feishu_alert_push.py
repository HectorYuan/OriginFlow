#!/usr/bin/env python3
"""feishu_alert_push.py — 漂移检测结果 → 飞书园区「漂移告警中心」doc (C2, 园区方案 §2.2)。

数据流: check_team_drift.py (真相) → 解析 ERROR/WARN → 告警中心 doc 增量段
幂等: 按 [日期] 查重 — 同日已有条目则跳过 (告警当日一次, 人工处置后可 --force 重推)
纪律: best-effort 失败不阻塞; 部署 cron/10min 可选。
用法: python3 scripts/feishu_alert_push.py [--force]"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DRIFT_SCRIPT = Path("/home/hector/DevSpace/OriginFlow/scripts/check_team_drift.py")
DOC = "Kf2SwPVnBiG2a7kuy5icfwDFnyF"  # 🚨 漂移告警中心
PY = "/home/hector/DevSpace/AgentSwarm/.venv/bin/python3"


def run_drift() -> tuple[int, int, list[str]]:
    r = subprocess.run([PY, str(DRIFT_SCRIPT)], capture_output=True, text=True)
    text = r.stdout + r.stderr
    m = re.search(r"ERROR (\d+) \| WARN (\d+)", text)
    errs = int(m.group(1)) if m else -1
    warns = int(m.group(2)) if m else 0
    details = [ln.strip() for ln in text.splitlines() if "[ERROR]" in ln][:8]
    return errs, warns, details


def lark(args: list[str]) -> dict:
    r = subprocess.run(["lark-cli", *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False}


def today_logged() -> bool:
    f = lark(["docs", "+fetch", "--as", "user", "--doc", DOC, "--scope", "keyword",
              "--keyword", f"[{date.today()}]", "--format", "json"])
    return f"[{date.today()}]" in str((f.get("data") or {}).get("document") or {})


def push(content: str) -> str:
    u = lark(["docs", "+update", "--as", "user", "--doc", DOC, "--command", "append",
              "--doc-format", "xml", "--content", content, "--format", "json"])
    return "ok" if u.get("ok") else f"FAIL:{str(u.get('error'))[:80]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    errs, warns, details = run_drift()
    if errs < 0:
        print("drift check failed to parse", file=sys.stderr)
        sys.exit(1)
    if today_logged() and not a.force:
        print("already logged today (idempotent skip; --force to override)")
        return
    today = date.today()
    if errs == 0:
        msg = (f"<p>✅ <b>[{today}] 巡检心跳</b> — ERROR 0 / WARN {warns} · 组织契约对齐</p>")
    else:
        lis = "".join(f"<li>{d}</li>" for d in details) or "<li>(明细略)</li>"
        msg = (f"<p>🚨 <b>[{today}] 漂移告警</b> — ERROR {errs} / WARN {warns}，需当日处置"
               f"（处置: OriginFlow scripts/sync_team_schema.py 重生投影 → 复检归零）</p><ul>{lis}</ul>")
    print(f"push {errs}E/{warns}W ->", push(msg))


if __name__ == "__main__":
    main()

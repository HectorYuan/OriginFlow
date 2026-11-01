#!/usr/bin/env python3
"""dashboard_data.py — NeoMachine 全局状态数据采集层 (四端共用)。

一份采集, 四端消费:
  TUI ANSI 看板 (watch 刷新)
  HTML 聚合页 (浏览器)
  飞书 Base 仪表盘 (Base 镜像)
  飞书群播报 (bot 消息)

数据源全部只读, 零外部依赖 (标准库 + pyyaml + tomllib)。
"""
from __future__ import annotations
import glob
import json
import os
import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

OF_ROOT = Path(__file__).resolve().parent.parent
AS_ROOT = OF_ROOT.parent / "AgentSwarm"
ZS_ROOT = OF_ROOT.parent / "ZenSwarm"
SCHEMA = Path("/home/hector/DevSpace/OriginForce/docs/team-schema.yaml")
AS_DB = AS_ROOT / ".swarm/dev/swarm.db"
HERDR_CHAT = "oc_868c2b79a4bfa24a18695350519aa009"


def _git_log(repo: Path, fmt: str, n: int = 10, extra: list[str] | None = None) -> list[str]:
    cmd = ["git", "-C", str(repo), "log", f"--format={fmt}", f"-{n}"]
    if extra: cmd.extend(extra)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return [l for l in r.stdout.strip().splitlines() if l]
    except Exception:
        return []


def _herdr_panes() -> list[dict]:
    try:
        r = subprocess.run(["herdr", "pane", "list"], capture_output=True, text=True, timeout=15)
        i = r.stdout.find("{")
        d = json.loads(r.stdout[i:])
        return d.get("result", {}).get("panes", [])
    except Exception:
        return []


def collect_schema() -> dict:
    """OriginForce schema → 席位/等级/梯队。"""
    import yaml
    try:
        d = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
        members = []
        for b in d.get("brand_teams", {}).values():
            members.extend(b.get("members", []))
        by_level = {}
        for m in members:
            lvl = m.get("level", "?")
            by_level.setdefault(lvl, []).append({
                "agent_id": m["agent_id"], "name": m.get("name", ""),
                "tier": m.get("capability_tier", ""), "runtime": m.get("runtime", ""),
                "status": m.get("status", "active"),
            })
        return {"total": len(members), "by_level": by_level, "members": members}
    except Exception as e:
        return {"error": str(e), "total": 0, "by_level": {}, "members": []}


def collect_zs_tasks() -> dict:
    """ZenSwarm .team/tasks/*.toml + git trailer → 任务流水。"""
    tasks = []
    for f in sorted(glob.glob(str(ZS_ROOT / ".team/tasks/*.toml"))):
        try:
            d = tomllib.load(open(f, "rb"))
            tasks.append({
                "task_id": d.get("id", ""), "title": (d.get("title") or "")[:80],
                "state": d.get("state", "draft"), "agent": d.get("agent", ""),
                "attempts": d.get("attempts", 0),
            })
        except Exception:
            pass
    # git trailer 补真实状态
    try:
        out = subprocess.run(
            ["git", "-C", str(ZS_ROOT), "log", "--format=%s", "--all", "-3000"],
            capture_output=True, text=True, timeout=15).stdout
        git_status = {}
        for line in out.splitlines():
            m = re.match(r"task\((T-\d+)\): (done|fail|create)", line)
            if m:
                tid, st = m.group(1), m.group(2)
                if tid not in git_status:
                    git_status[tid] = "done" if st == "done" else ("fail" if st.startswith("fail") else "wip")
        for t in tasks:
            tid = t["task_id"]
            if tid in git_status:
                t["state"] = git_status[tid]
    except Exception:
        pass
    from collections import Counter
    states = Counter(t["state"] for t in tasks)
    return {"total": len(tasks), "states": dict(states), "tasks": tasks}


def collect_as_db() -> dict:
    """AgentSwarm DB → proposals/tasks/milestones 计数。"""
    import sqlite3
    result = {}
    try:
        con = sqlite3.connect(f"file:{AS_DB}?mode=ro", uri=True, timeout=10)
        for table in ("proposals", "tasks", "milestones"):
            try:
                n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                result[table] = n
            except Exception:
                result[table] = 0
        # proposal 状态分布
        try:
            rows = con.execute("SELECT status, COUNT(*) FROM proposals GROUP BY status ORDER BY COUNT(*) DESC").fetchall()
            result["proposal_states"] = dict(rows)
        except Exception:
            result["proposal_states"] = {}
        con.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def collect_drift() -> dict:
    """drift 检测结果 (读 OriginFlow 侧缓存或跑一次)。"""
    try:
        r = subprocess.run(
            ["python3", str(OF_ROOT / "scripts/check_team_drift.py")],
            capture_output=True, text=True, timeout=30, cwd=str(OF_ROOT))
        m = re.search(r"ERROR (\d+)", r.stdout)
        errors = int(m.group(1)) if m else -1
        return {"errors": errors, "ok": errors == 0, "raw": r.stdout.strip()[-200:]}
    except Exception as e:
        return {"errors": -1, "ok": False, "error": str(e)}


def collect_bridge() -> dict:
    """bus-bridge.state + 飞书群状态。"""
    state_file = ZS_ROOT / ".team/bus-bridge.state"
    last_ts = 0
    if state_file.exists():
        try:
            last_ts = int(state_file.read_text().strip())
        except Exception:
            pass
    return {
        "last_ts": last_ts,
        "last_sync": datetime.fromtimestamp(last_ts).strftime("%m-%d %H:%M") if last_ts else "-",
        "chat_id": HERDR_CHAT,
    }


def collect_events(n: int = 15) -> list[dict]:
    """跨域最近事件流 (AS git + ZS git)。"""
    events = []
    zs_log = _git_log(ZS_ROOT, "%h|%ad|%s", n, ["--date=format:%m-%d %H:%M", "--grep=task(T-"])
    for l in zs_log:
        parts = l.split("|", 2)
        if len(parts) == 3:
            emoji = "🟢" if "done" in parts[2] else ("🔴" if "fail" in parts[2] else "🔵")
            events.append({"source": "ZS", "emoji": emoji, "text": parts[2][:80], "sha": parts[0]})
    as_log = _git_log(AS_ROOT, "%h|%ad|%s", n, ["--date=format:%m-%d %H:%M"])
    for l in as_log:
        parts = l.split("|", 2)
        if len(parts) == 3:
            events.append({"source": "AS", "emoji": "📜", "text": parts[2][:80], "sha": parts[0]})
    events.sort(key=lambda x: x.get("sha", ""), reverse=True)
    return events[:n]


def collect_herdr() -> dict:
    """herdr pane → workspace/agent 状态。"""
    panes = _herdr_panes()
    by_ws = {}
    for p in panes:
        wid = p.get("workspace_id", "?")
        by_ws.setdefault(wid, []).append({
            "pane_id": p.get("pane_id", ""), "label": p.get("label", ""),
            "agent": p.get("agent", ""), "status": p.get("agent_status", "?"),
        })
    return {"total": len(panes), "by_workspace": dict(by_ws)}


def collect_all() -> dict:
    """主入口 — 返回全量状态 dict。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "timestamp": now,
        "schema": collect_schema(),
        "zs_tasks": collect_zs_tasks(),
        "as_db": collect_as_db(),
        "drift": collect_drift(),
        "bridge": collect_bridge(),
        "events": collect_events(),
        "herdr": collect_herdr(),
    }


if __name__ == "__main__":
    import sys
    data = collect_all()
    out = json.dumps(data, ensure_ascii=False, indent=1, default=str)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(out, encoding="utf-8")
        print(f"written: {sys.argv[1]} ({len(out)} B)")
    else:
        print(out)

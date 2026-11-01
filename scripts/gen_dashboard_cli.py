#!/usr/bin/env python3
"""gen_dashboard_cli.py — TUI ANSI 彩色看板 (herdr pane 内 watch -n 60 刷新)。

用法:
  python3 scripts/gen_dashboard_cli.py                    # 单次输出
  watch -n 60 python3 scripts/gen_dashboard_cli.py       # 60s 自动刷新
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dashboard_data import collect_all

# ANSI codes
R = "\033[0m"
B = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BORDER = "\033[90m"

W = 72  # 看板宽度

def line(char="─", color=BORDER):
    return f"{color}{char * W}{R}"

def section(title, color=CYAN):
    return f"\n{color}{B}  {title}{R}\n{line('─', color)}"

def kv(key, val, key_color=WHITE, val_color=GREEN, pad=16):
    return f"  {key_color}{key:<{pad}}{R} {val_color}{val}{R}"

def main():
    d = collect_all()
    print(f"{BG_BLUE}{WHITE}{B}{'NeoMachine 数字公司':^{W}}{R}")
    print(f"{DIM}  {d['timestamp']}{R}")
    print(line("═", CYAN))

    # ── 状态条 ──
    drift_ok = d["drift"].get("ok", False)
    drift_color = GREEN if drift_ok else RED
    drift_text = "0 ERROR ✓" if drift_ok else f"{d['drift'].get('errors','?')} ERROR ✗"
    zs = d["zs_tasks"].get("states", {})
    done = zs.get("done", 0); wip = zs.get("wip", 0); fail = zs.get("fail", 0)
    proposals = d["as_db"].get("proposals", 0)
    seats = d["schema"].get("total", 0)
    panes = d["herdr"].get("total", 0)
    bridge = d["bridge"].get("last_sync", "-")

    print(f"\n{B}  ── 全局状态 ──{R}")
    print(f"  {kv('席位', str(seats))}  {kv('herdr panes', str(panes))}")
    print(f"  {kv('ZS 任务 done', str(done), val_color=GREEN)}  {kv('wip', str(wip), val_color=YELLOW)}  {kv('fail', str(fail), val_color=RED)}")
    print(f"  {kv('AS proposals', str(proposals))}  {kv('漂移', drift_text, val_color=drift_color)}")
    print(f"  {kv('桥最后同步', bridge, key_color=DIM, val_color=CYAN)}")

    # ── 六层体系 ──
    print(section("六层体系"))
    layers = [
        ("L5 集成", "OriginFlow", "生成器 + 漂移检测 + 桥 + site", CYAN),
        ("L4 情报", "research + radar + DesignCanon", "21 报告 + 347 公理", MAGENTA),
        ("L3 治理", "AgentSwarm", f"提案 {proposals} · FSM 门禁 · 蒸馏", BLUE),
        ("L2 组织", "OriginForce", f"schema v2.0 · {seats} 席位 · 飞书映射", GREEN),
        ("L1 执行", "ZenSwarm", f"{d['zs_tasks']['total']} 任务 · git 权威 · loop2green", YELLOW),
        ("L0 呈现", "herdr + zcode", f"{panes} pane · 15 agent-cards", WHITE),
    ]
    for name, repo, desc, c in layers:
        print(f"  {c}{B}● {name}{R} {repo:20s} {DIM}{desc}{R}")

    # ── 席位梯队 ──
    print(section("席位梯队"))
    schema = d.get("schema", {})
    for lvl in ["L5", "L4", "L3", "L2", "L1"]:
        seats = schema.get("by_level", {}).get(lvl, [])
        if not seats: continue
        ids = [s["agent_id"] for s in seats]
        tier = seats[0].get("tier", "?")
        color = {"L5": RED, "L4": MAGENTA, "L3": CYAN, "L2": GREEN, "L1": WHITE}.get(lvl, WHITE)
        print(f"  {color}{B}{lvl:>3}{R} {DIM}({tier}){R} {', '.join(ids)}")

    # ── ZS 任务状态分布 ──
    print(section("ZenSwarm 任务状态"))
    total_zs = d["zs_tasks"].get("total", 0)
    for state in ["done", "wip", "verify", "draft", "ready", "fail", "dropped"]:
        n = zs.get(state, 0)
        if n == 0: continue
        bar_len = int(n / total_zs * 30) if total_zs else 0
        c = {"done": GREEN, "wip": YELLOW, "verify": BLUE, "draft": DIM,
             "ready": CYAN, "fail": RED, "dropped": DIM}.get(state, WHITE)
        bar = f"{c}{'█' * bar_len}{R}{'░' * (30 - bar_len)}"
        print(f"  {state:>8} {bar} {n:>4}/{total_zs}")

    # ── 漂移状态 ──
    drift = d.get("drift", {})
    if not drift.get("ok", False):
        print(f"\n  {RED}{B}⚠️ drift 检测异常{R}")

    # ── 最近事件流 ──
    print(section("最近事件"))
    for e in d.get("events", [])[:10]:
        src = e.get("source", "?")
        emoji = e.get("emoji", "📜")
        text = e.get("text", "")[:65]
        src_color = CYAN if src == "ZS" else BLUE
        print(f"  {emoji} {src_color}[{src}]{R} {text}")

    # ── herdr workspace 状态 ──
    print(section("Workspace"))
    herdr_ws = d.get("herdr", {}).get("by_workspace", {})
    ws_names = {"wW": "OriginForce/CEO", "w0": "OriginFlow", "wY": "ZenSwarm",
                "wR": "AgentSwarm", "wN": "DevSpace", "wZ": "监控"}
    for wid in ["wW", "w0", "wY", "wR", "wN", "wZ"]:
        panes = herdr_ws.get(wid, [])
        if not panes: continue
        active = [p for p in panes if p.get("status") in ("idle", "working")]
        labels = [p.get("label", "?") for p in active]
        name = ws_names.get(wid, wid)
        print(f"  {CYAN}{wid}{R} {name:20s} {len(active)}/{len(panes)} active  {DIM}{', '.join(labels[:4])}{'...' if len(labels) > 4 else ''}{R}")

    print(f"\n{line('═', CYAN)}")
    print(f"{DIM}  gen_dashboard_cli.py · watch -n 60 刷新 · NeoMachine 六层体系{R}\n")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""gen_site.py — NeoMachine site 静态生成器 (L5 集成层, 归 w0:p1)。

管线: schema v2.0 (yaml.safe_load) → ZS .team/tasks/*.toml (tomllib)
      → git log (subprocess) → drift (check_team_drift.py) → site/*.html
约束: ≤200 行 · 仅标准库 + pyyaml + tomllib · 零 JS 框架 (site-architecture.md §3.4)
幂等: 目标文件已存在则跳过不覆盖 — dashboard.html 与三子页由 w0:p3 omp 填充。"""
import argparse, json, re, sqlite3, subprocess, tomllib
from datetime import datetime
from html import escape
from pathlib import Path

import yaml

OF = Path(__file__).resolve().parent.parent
SITE = OF / "site"
ZS = OF.parent / "ZenSwarm"
AS = OF.parent / "AgentSwarm"
SCHEMA = Path("/home/hector/DevSpace/OriginForce/docs/team-schema.yaml")

# 六层体系 (真相源: gen_dashboard_cli.py 同款口径)
LAYERS = [
    ("L5 集成", "OriginFlow", "生成器 + 漂移检测 + 桥 + site"),
    ("L4 情报", "research + radar + DesignCanon", "21 报告 + 347 公理"),
    ("L3 治理", "AgentSwarm", "提案 {props} · FSM 门禁 · 蒸馏"),
    ("L2 组织", "OriginForce", "schema v2.0 · {seats} 席位 · 飞书映射"),
    ("L1 执行", "ZenSwarm", "{ntasks} 任务 · git 权威 · loop2green"),
    ("L0 呈现", "herdr + zcode", "pane · agent-cards"),
]
TIER = {"L5": "elite", "L4": "expert", "L3": "specialist", "L2": "consultant", "L1": "utility"}
ZEN = [("https://site.zenlearning.cn/arch/", "ZenSwarm 组件图 36 页"),
       ("https://site.zenlearning.cn/radar/", "情报雷达"),
       ("https://site.zenlearning.cn/misc/designcanon/", "DesignCanon 347 公理")]

CSS = """:root{--bg:oklch(0.17 0.012 232);--surface:oklch(0.205 0.013 232);--fg:oklch(0.93 0.006 200);--muted:oklch(0.66 0.014 220);--accent:oklch(0.82 0.14 168);--border:oklch(0.30 0.015 225);--serif:Georgia,"Noto Serif SC",serif;--sans:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;--mono:"SF Mono",Menlo,Consolas,monospace;--maxw:1160px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);line-height:1.65}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
header{border-bottom:1px solid var(--border)}header .wrap{display:flex;justify-content:space-between;align-items:center;padding-top:14px;padding-bottom:14px}
.brand{font-family:var(--serif);font-size:19px;font-weight:700;color:var(--fg)}
nav a{margin-left:18px;color:var(--muted);font-size:14px}nav a.on,nav a:hover{color:var(--accent)}
h1{font-family:var(--serif);font-size:42px;margin:44px 0 10px;letter-spacing:.01em}
h2{font-family:var(--serif);font-size:24px;margin:44px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.lede{color:var(--muted);font-size:16px;max-width:720px}
.grid{display:grid;gap:14px}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:820px){.g3,.g2{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.card h3{margin:0 0 6px;font-size:15px}.card p{margin:0;color:var(--muted);font-size:13.5px}
.tag{display:inline-block;font-family:var(--mono);font-size:11.5px;color:var(--accent);border:1px solid var(--border);border-radius:99px;padding:1px 9px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:500;font-size:12px}.mono{font-family:var(--mono);font-size:13px}
.stats{display:flex;gap:32px;margin:26px 0 0;flex-wrap:wrap}.stat b{font-family:var(--mono);font-size:26px;color:var(--accent);display:block}.stat span{color:var(--muted);font-size:13px}
.cta{margin:22px 0 0;display:flex;gap:12px;flex-wrap:wrap}.cta a{border:1px solid var(--border);background:var(--surface);border-radius:8px;padding:8px 18px;font-size:14px}.cta a:hover{border-color:var(--accent);text-decoration:none}
.todo{border:1px dashed var(--border);border-radius:10px;padding:38px;text-align:center;color:var(--muted);margin-top:16px}footer{margin:56px 0 30px;padding-top:14px;border-top:1px solid var(--border);color:var(--muted);font-size:12.5px}
.ev{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--border);font-size:13.5px}.ev time{font-family:var(--mono);color:var(--muted);white-space:nowrap}.ev .src{font-family:var(--mono);font-size:11.5px;color:var(--accent)}
"""

NAV = [("index.html", "门户"), ("dashboard.html", "总控台"), ("team/index.html", "名册"), ("intel/index.html", "情报"), ("cases/index.html", "案例")]


# ── 数据管线 (四源只读) ──────────────────────────────────────────
def git_events(n: int = 10) -> list[dict]:
    ev = []
    for repo, src in ((ZS, "ZS"), (AS, "AS")):
        try:
            r = subprocess.run(["git", "-C", str(repo), "log", "--format=%ad|%s", "--date=format:%m-%d %H:%M", f"-{n * 2}"], capture_output=True, text=True, timeout=15)
            for line in r.stdout.strip().splitlines():
                if "|" in line:
                    ts, subj = line.split("|", 1)
                    ev.append({"ts": ts, "subj": escape(subj[:100]), "src": src})
        except Exception:
            pass
    ev.sort(key=lambda e: e["ts"], reverse=True)
    return ev[:n]


def load_events(n: int = 10) -> list[dict]:
    """事件流优先读 site/dashboard-data.json (与 dashboard.html 同源); 缺文件回落 git_events。"""
    try:
        data = json.loads((SITE / "dashboard-data.json").read_text(encoding="utf-8"))
        evs = [{"ts": str(e.get("sha", ""))[:7], "subj": escape(str(e.get("text", ""))[:100]),
                "src": e.get("source", "")} for e in data.get("events", [])[:n]]
        return evs
    except Exception:
        return git_events(n)


def load_tasks() -> dict:
    tasks = []
    for f in sorted((ZS / ".team/tasks").glob("*.toml")):
        try:
            d = tomllib.load(open(f, "rb"))
            tasks.append({"id": d.get("id", ""), "title": (d.get("title") or "")[:80], "state": d.get("state", "draft"), "agent": d.get("agent", "")})
        except Exception:
            pass
    from collections import Counter
    return {"total": len(tasks), "states": dict(Counter(t["state"] for t in tasks)), "tasks": tasks}


def load_members() -> list[dict]:
    d = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    return [m for b in d.get("brand_teams", {}).values() for m in b.get("members", [])]


def drift_errors() -> int:
    try:
        r = subprocess.run(["python3", str(OF / "scripts/check_team_drift.py")], capture_output=True, text=True, timeout=60, cwd=OF)
        m = re.search(r"ERROR (\d+)", r.stdout)
        return int(m.group(1)) if m else -1
    except Exception:
        return -1


def as_proposals() -> int:
    try:
        with sqlite3.connect(f"file:{AS / '.swarm/dev/swarm.db'}?mode=ro", uri=True, timeout=10) as con:
            return con.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
    except Exception:
        return 0


# ── 渲染 ────────────────────────────────────────────────────────
def page(title: str, body: str, active: str) -> str:
    nav = "".join(f'<a href="/{h}"{" class=on" if h == active else ""}>{t}</a>' for h, t in NAV)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · NeoMachine 数字公司</title><style>{CSS}</style></head>
<body><header><div class="wrap"><a class="brand" href="/">NeoMachine 数字公司</a><nav>{nav}</nav></div></header>
<main class="wrap">{body}
<footer>gen_site.py 生成 · {now} · NeoMachine 六层体系 · 数据源 schema v2.0 / ZS git / drift</footer>
</main></body></html>"""


def build_context() -> dict:
    members = load_members()
    zt = load_tasks()
    by_level: dict[str, list] = {}
    for m in members:
        by_level.setdefault(m.get("level", "?"), []).append(m)
    return {"members": members, "by_level": by_level, "zs": zt, "props": as_proposals(), "drift": drift_errors(), "events": load_events(10)}


def layer_cards(ctx: dict) -> str:
    fmt = {"props": ctx["props"], "seats": len(ctx["members"]), "ntasks": ctx["zs"]["total"]}
    return "".join(f'<div class="card"><h3><span class="tag">{lv}</span> {repo}</h3><p>{desc.format(**fmt)}</p></div>' for lv, repo, desc in LAYERS)


def seat_card(m: dict) -> str:
    return f'<div class="card"><h3>{escape(m.get("name") or m["agent_id"])}</h3><p><span class="tag">{m["agent_id"]}</span> {m.get("capability_tier", "")}</p><p class="mono">{m.get("runtime", "")} · {escape(m.get("role", ""))}</p></div>'


def nav_cards() -> str:
    sub = [("dashboard.html", "聚合总控台", "五域实时状态一屏"), ("team/index.html", "数字员工名册", "17 席位卡片 · 三视图"), ("intel/index.html", "情报索引", "research + radar + DesignCanon"), ("cases/index.html", "落地案例", "恢复/漂移/桥 实战复盘")]
    cards = "".join(f'<div class="card"><h3><a href="/{h}">{t} →</a></h3><p>{d}</p></div>' for h, t, d in sub)
    cards += "".join(f'<div class="card"><h3><a href="{u}">{t} ↗</a></h3><p>zenlearning 域</p></div>' for u, t in ZEN)
    return f'<div class="grid g3">{cards}</div>'


def render_index(ctx: dict) -> str:
    """门户主页 (T-203): hero + CTA + 六层卡 + 席位梯队 + 最近事件 + 导航。"""
    stats = (f'<div class="stats"><div class="stat"><b>{len(ctx["members"])}</b><span>席位</span></div>'
             f'<div class="stat"><b>{ctx["zs"]["total"]}</b><span>ZenSwarm 任务</span></div>'
             f'<div class="stat"><b>{ctx["props"]}</b><span>AS 提案</span></div>'
             f'<div class="stat"><b>{"0 ✓" if ctx["drift"] == 0 else ctx["drift"]}</b><span>漂移 ERROR</span></div></div>')
    tiers = "".join(f'<h2>{lv} 梯队 <span class="tag">{TIER[lv]}</span></h2><div class="grid g3">'
                    + "".join(seat_card(m) for m in ctx["by_level"][lv]) + "</div>"
                    for lv in ("L5", "L4", "L3", "L2", "L1") if ctx["by_level"].get(lv))
    evs = "".join(f'<div class="ev"><time>{e["ts"]}</time><span class="src">[{e["src"]}]</span><span>{e["subj"]}</span></div>' for e in ctx["events"])
    cta = "".join(f'<a href="/{h}">{t}</a>' for h, t in NAV[1:])
    body = f"""<h1>NeoMachine 数字公司</h1>
<p class="lede">六层 agent 体系 · {len(ctx["members"])} 数字员工席位 · 从 L5 集成到 L0 呈现的一体化数字组织。</p>
<div class="cta">{cta}</div>{stats}
<h2>六层体系</h2><div class="grid g3">{layer_cards(ctx)}</div>
{tiers}
<h2>最近事件</h2>{evs}
<h2>导航 · 四子页 + zenlearning 域</h2>{nav_cards()}"""
    return page("门户", body, "index.html")


PAGES = [
    ("dashboard.html", "总控台", "dashboard.html", "聚合总控台", "五域实时状态一屏 — 由 w0:p3 omp 填充 (gen_dashboard.py)"),
    ("team/index.html", "数字员工名册", "team/index.html", "数字员工名册", "17 席位卡片 · 梯队/看板/关联三视图 — 由 w0:p3 omp 填充"),
    ("intel/index.html", "情报索引", "intel/index.html", "情报索引", "research + radar + DesignCanon 三层导航 — 由 w0:p3 omp 填充"),
    ("cases/index.html", "落地案例", "cases/index.html", "落地案例", "恢复/漂移/桥 三篇实战复盘 — 由 w0:p3 omp 填充"),
]


def main() -> None:
    ctx = build_context()
    for d in ("", "team", "intel", "cases"):
        (SITE / d).mkdir(exist_ok=True)
    idx = SITE / "index.html"
    if not idx.exists():
        idx.write_text(render_index(ctx), encoding="utf-8")
        print(f"gen  {idx}")
    else:
        print(f"skip {idx} (已存在, 不覆盖)")
    for rel, title, active, h1, todo in PAGES:
        p = SITE / rel
        if p.exists():
            print(f"skip {p} (已存在, 不覆盖)")
            continue
        body = f'<h1>{h1}</h1><p class="lede">NeoMachine 六层体系子页。</p><div class="todo">{todo}</div>'
        p.write_text(page(title, body, active), encoding="utf-8")
        print(f"gen  {p}")


if __name__ == "__main__":
    main()

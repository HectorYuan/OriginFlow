#!/usr/bin/env python3
"""gen_hq_registry.py — 数字总部页生成器 (Registry 聚合的呈现投影)。

管线: 读 OriginForce/docs/hq-registry.yaml (聚合根真相) + 各仓 INDEX.md frontmatter (I4 合规快照)
      → 渲染 site/hq/index.html (四类实体总览; tool_layer 条目只渲染链接卡, I2)
复用: gen_site.page()/CSS — 共享 hq.css 组件与全站导航 (Published Language)
约束: ≤120 行 · 仅标准库 + pyyaml · 遵循 domain-model I1-I4 (digital-hq-domain-model-v1.md §2.3)"""
import sys
from datetime import date
from html import escape
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_site as gs  # noqa: E402  (共享 page()/CSS; __main__ 守卫安全)

OF = Path(__file__).resolve().parent.parent
REG = Path("/home/hector/DevSpace/OriginForce/docs/hq-registry.yaml")
COLLECTIONS = [  # (registry id, INDEX.md 相对 repo 路径, 一行定位)
    ("originforce-docs", "/home/hector/DevSpace/OriginForce/docs/INDEX.md", "组织契约文档集"),
    ("originforce-agents", "/home/hector/DevSpace/OriginForce/docs/INDEX.md", "席位身份包体系"),
    ("originflow-adr", OF / "docs/adr/INDEX.md", "架构决策记录"),
    ("originflow-cases", OF / "docs/cases/INDEX.md", "落地案例复盘"),
    ("originflow-design", OF / "docs/design/INDEX.md", "设计文档"),
    ("originflow-intel", OF / "docs/intel/INDEX.md", "情报参谋部索引(兼编 AS 集合)"),
    ("originflow-architecture", OF / "docs/architecture/INDEX.md", "架构图集"),
    ("originflow-generated", OF / "docs/generated/INDEX.md", "生成投影镜像"),
    ("agentswarm-research", OF / "docs/intel/INDEX.md", "AS 调研报告(经 intel 编目)"),
]


def _fm(p: str | Path) -> dict:
    """轻解析 INDEX.md YAML frontmatter (spec §2 五字段), 缺失返回空。"""
    try:
        t = Path(p).read_text(encoding="utf-8")
    except OSError:
        return {}
    if not t.startswith("---") or (end := t.find("---", 3)) < 0:
        return {}
    try:
        return yaml.safe_load(t[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _backlink_ok(p: str | Path) -> bool:
    p = Path(p)
    return "**总部入口**" in (p.read_text(encoding="utf-8") if p.exists() else "")


def render(reg: dict) -> str:
    projs = "".join(
        f'<div class="card"><h3><span class="tag">{escape(p["layer"])}</span> {escape(p["id"])}</h3>'
        f'<p>{escape(p["role"])}</p><p class="mono">{escape(str(p.get("overview_page", "")))}</p></div>'
        for p in reg.get("projects", []))
    kns = "".join(
        f'<div class="card"><h3>{escape(k["id"])}{" <span class=\"tag tool\">通用工具层</span>" if k.get("tool_layer") else ""}</h3>'
        f'<p class="mono">{escape(str(k["truth_source"]["repo"]))}/{escape(str(k["truth_source"]["path"]))}</p>'
        f'<p>{("纯链接引用 · 禁复制 (I2)" if k.get("tool_layer") else " · ".join(k.get("consumers", [])))}</p></div>'
        for k in reg.get("knowledge", []))
    tasks = "".join(
        f'<div class="ev"><time class="mono">{escape(t["source"])}</time><span class="src">[指针]</span>'
        f'<span>{escape(t["ref"])} · 实时查询: {escape(t["status_query"])}</span></div>'
        for t in reg.get("tasks", []))
    hq_skills = [s for s in reg.get("skills", []) if isinstance(s.get("name"), str)]
    sks = (f'<div class="card"><h3>技能真相源 <span class="tag">agentswarm-skills</span></h3>'
           f'<p class="mono">AgentSwarm/skills/ → ~/.agents/skills + ~/.zcode 镜像</p></div>'
           + "".join(f'<div class="card"><h3>hq-{escape(s["name"])}</h3><p class="mono">{escape(str(s.get("yaml_path", "")))}</p></div>'
                     for s in hq_skills))
    feeds = "".join(
        f'<div class="card"><h3>{escape(f["source"])} <span class="tag tool">二期 Feed</span></h3>'
        f'<p class="mono">{escape(str(f["ref"]))}</p></div>'
        for f in reg.get("feed_candidates", []))
    # v1.1 Feed 段: 指南宇宙知识空间 (I5 只存指针; mirror 节点出链接卡)
    feed = reg.get("feeds", {})
    feed_cards = "".join(
        f'<div class="card"><h3>{escape(e["name"])} <span class="tag tool">{escape(e.get("direction", "inbound"))}</span></h3>'
        + (f'<p class="mono"><a href="{escape(e["mirror_url"])}">数字总部镜像节点 ↗</a></p>' if e.get("mirror_url")
           else f'<p class="mono">space {escape(str(e["space_id"]))}</p>')
        + f'<p>{escape(str(e.get("note", "") or ""))}</p></div>'
        for e in feed.get("entries", []))
    inv = " · ".join(escape(str(v)) for v in reg.get("invariants", {}).values())
    inv += " · I5 Feed 不搬运（v1.1）"
    checked = sum(1 for _, p, _ in COLLECTIONS if _fm(p) and _backlink_ok(p))
    body = f"""<h1>数字总部</h1>
<p class="lede">组织资产的注册、路由与呈现中枢（Registry of Record）· OriginFlow 内 Bounded Context · 只登记真相位置，永不复制资产内容。</p>
<div class="cta"><a href="/dashboard.html">总控台</a><a href="/intel/index.html">情报</a><a href="https://github.com/">域模型</a></div>
<div class="stats"><div class="stat"><b>{len(reg.get("projects", []))}</b><span>项目</span></div>
<div class="stat"><b>{len(reg.get("knowledge", []))}</b><span>知识库集合</span></div>
<div class="stat"><b>{len(reg.get("tasks", []))}</b><span>任务指针源</span></div>
<div class="stat"><b>{len(feed.get("entries", []))}</b><span>外部 Feed</span></div>
<div class="stat"><b>{checked}/{len(COLLECTIONS)}</b><span>总览合规 (I4)</span></div></div>
<h2>项目 · Registry projects</h2><div class="grid g3">{projs}</div>
<h2>知识库集合 · Registry knowledge</h2><div class="grid g3">{kns}</div>
<h2>任务指针 · 不落状态 (I3)</h2>{tasks}
<h2>技能 · Registry skills</h2><div class="grid g3">{sks}</div>
<h2>外部 Feed · 指南宇宙知识库打通 (I5)</h2><div class="grid g3">{feed_cards}</div>
<h2>Feed 候选 · 按需后补</h2><div class="grid g3">{feeds}</div>
<h2>聚合不变量</h2><p class="lede">{inv}</p>"""
    return gs.page("总部", body, "hq/index.html")


def main() -> None:
    reg = yaml.safe_load(REG.read_text(encoding="utf-8"))
    out = OF / "site/hq/index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(reg), encoding="utf-8")
    print(f"gen  {out}  (registry v{reg.get('version')} · {date.today()})")


if __name__ == "__main__":
    main()

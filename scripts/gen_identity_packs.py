#!/usr/bin/env python3
"""gen_identity_packs.py — 为 schema 17 席位生成 OriginForce 身份包骨架 (A2)。

产出: OriginForce/agents/<agent_id>/ 下 7 文件骨架
  IDENTITY.md (从 AS definitions frontmatter 提取, 自动填充)
  META.json   (机器可读映射, 自动填充)
  USER.md     (共享模板, 一次性生成)
  MEMORY.md   (空骨架, 人工填充)
  TOOLS.md    (从 AS definitions depends_on/mcp 提取, 自动填充)
  EVOLUTION.md(空骨架)
  DAILY.md    (空骨架)

幂等: 已存在的文件不覆盖 (除非 --force)。
"""
from __future__ import annotations
import json, re, sys, yaml
from pathlib import Path
from datetime import datetime

OF_ROOT = Path(__file__).resolve().parent.parent
OF = OF_ROOT.parent / "OriginForce"
AS = OF.parent / "AgentSwarm"
SCHEMA = OF / "docs" / "team-schema.yaml"

USER_TEMPLATE = """# USER · 主人画像

> Hector — 所有 agent 共享的主人画像。此文件为只读投影，真相源在 solution-expert/USER.md。

## 基本信息

- **名字 / 称呼**：Hector
- **GitHub**：HectorYuan

## 角色与背景

- **AI/数智化转型领域专业人士**
- **当前状态**：构建 NeoMachine 数字公司（五域协作体系）
- **偏好**：专业、务实、有深度；结论先行 + 事实必验；极简指令

## 互动偏好

- 说"继续"= 按方案执行
- 说"核对"= 重新验证所有结论
- 反馈直接具体，不绕弯
- 非核心决策不需要逐个请示，留档即可
"""

MEMORY_TEMPLATE = """# MEMORY · {name} 长期记忆

> 行为规则 + 工作方法论 + Hector 反馈。每次 task done 后追加。

## 长期行为规则

- **结论先行 + 事实必验**
- **高风险先确认**
- **Hector 反馈记录**：

## 工作方法论

（随任务积累，蒸馏后追加）

## 已知坑

（随实战发现追加）
"""

TOOLS_TEMPLATE = """# TOOLS · {name} 工具锚点

## CLI 工具

{cli_tools}

## MCP 工具

{mcp_tools}

## 委派队友

| 场景 | 委派给 | 备注 |
|---|---|---|
"""

EVOLUTION_TEMPLATE = """# EVOLUTION · {name} 演化轨迹

| 日期 | 事件 |
|---|---|
| {created} | 身份包初始化 |
"""

DAILY_TEMPLATE = """# DAILY · {name} 当前状态

| 项 | 值 |
|---|---|
| 当前任务 | - |
| 状态 | idle |
| 阻塞 | 无 |
| 更新时间 | - |
"""

IDENTITY_TEMPLATE = """# IDENTITY · {name}

> 真相源: AgentSwarm/agents/definitions/{agent_id}.md · 本文件由 sync_team_schema.py 生成骨架

## 名字与定位

- **名字**：{name}
- **角色定位**：{description}
- **等级**：{level}
- **能力档**：{capability_tier}
- **自主范围**：{autonomy_scope}
- **运行时**：{runtime}

## 职责

{职责}

## 可编排

{can_orchestrate}
"""


def extract_as_definition(agent_id: str) -> dict | None:
    """从 AS definitions/*.md 提取 frontmatter + body。"""
    path = AS / "agents" / "definitions" / f"{agent_id}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # 提取 frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not fm_match:
        return None
    import yaml
    try:
        fm = yaml.safe_load(fm_match.group(1))
    except Exception:
        fm = {}
    body = fm_match.group(2).strip()
    return {"frontmatter": fm, "body": body, "description": fm.get("description", "")}


def generate_identity_pack(agent_id: str, member: dict, force: bool = False):
    target = OF / "agents" / agent_id
    target.mkdir(parents=True, exist_ok=True)

    name = member.get("name", agent_id)
    level = member.get("level", "?")
    tier = member.get("capability_tier", "?")
    scope = member.get("autonomy_scope", "?")
    runtime = member.get("runtime", "?")
    orch = member.get("can_orchestrate", [])
    desc = member.get("description", "") or member.get("role", "")

    created = datetime.now().strftime("%Y-%m-%d")

    def wf(filename: str, content: str) -> bool:
        fp = target / filename
        if fp.exists() and not force:
            return False
        fp.write_text(content, encoding="utf-8")
        return True

    results = []

    # ── META.json ──
    meta = {
        "schema": "originforce-agent-identity/v2.0",
        "agent": {
            "name": name, "role": desc,
            "agent_id": agent_id, "level": level,
            "capability_tier": tier, "autonomy_scope": scope,
            "runtime": runtime,
            "can_orchestrate": orch,
            "memory_type": member.get("memory", "task"),
            "team": member.get("team", "brand:originforce"),
        },
        "files": {
            "IDENTITY.md": "角色定义摘要", "MEMORY.md": "长期记忆",
            "TOOLS.md": "工具锚点", "USER.md": "主人画像",
            "EVOLUTION.md": "演化轨迹", "DAILY.md": "状态快照",
        },
        "bindings": {
            "as_definition": f"AgentSwarm/agents/definitions/{agent_id}.md",
            "zs_agent_toml": f"ZenSwarm/.team/agents/{agent_id}.toml",
            "herdr_pane_title": f"{agent_id} @ <task>",
            "zcode_agent_card": f"~/.zcode/agent-cards/{agent_id}.json",
        },
        "generated_by": "sync_team_schema.py / gen_identity_packs.py",
        "generated_at": created,
    }
    if wf("META.json", json.dumps(meta, ensure_ascii=False, indent=2)):
        results.append("META.json")

    # ── IDENTITY.md ──
    as_def = extract_as_definition(agent_id)
    orch_str = "\n".join(f"- {x}" for x in orch) if orch else "- 无（不可编排其他 agent）"
    identity = IDENTITY_TEMPLATE.format(
        name=name, agent_id=agent_id, description=desc,
        level=level, capability_tier=tier,
        autonomy_scope=scope, runtime=runtime,
        can_orchestrate=orch_str,
        职责=desc,
    )
    if wf("IDENTITY.md", identity):
        results.append("IDENTITY.md")

    # ── USER.md (共享模板) ──
    if wf("USER.md", USER_TEMPLATE):
        results.append("USER.md")

    # ── MEMORY.md ──
    if wf("MEMORY.md", MEMORY_TEMPLATE.format(name=name)):
        results.append("MEMORY.md")

    # ── TOOLS.md ──
    cli_tools = "-"
    mcp_tools = "-"
    if as_def:
        fm = as_def["frontmatter"]
        deps = fm.get("depends_on", {})
        if isinstance(deps, dict):
            cli_list = deps.get("cli", [])
            if cli_list:
                cli_tools = "\n".join(f"| {c} |" for c in cli_list)
                cli_tools = f"| 命令 |\n|---|\n{cli_tools}"
            mcp_list = deps.get("mcp", [])
            if mcp_list:
                mcp_tools = "\n".join(f"| {x} |" for x in mcp_list)
                mcp_tools = f"| MCP 工具 |\n|---|\n{mcp_tools}"
    tools = TOOLS_TEMPLATE.format(name=name, cli_tools=cli_tools, mcp_tools=mcp_tools)
    if wf("TOOLS.md", tools):
        results.append("TOOLS.md")

    # ── EVOLUTION.md ──
    if wf("EVOLUTION.md", EVOLUTION_TEMPLATE.format(name=name, created=created)):
        results.append("EVOLUTION.md")

    # ── DAILY.md ──
    if wf("DAILY.md", DAILY_TEMPLATE.format(name=name)):
        results.append("DAILY.md")

    return results


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已有文件")
    ap.add_argument("--agent-id", help="只处理指定席位")
    args = ap.parse_args()

    import yaml
    d = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    members = []
    for b in d.get("brand_teams", {}).values():
        members.extend(b.get("members", []))

    if args.agent_id:
        members = [m for m in members if m["agent_id"] == args.agent_id]

    print(f"生成身份包: {len(members)} 席位 (force={args.force})")
    for m in members:
        aid = m["agent_id"]
        results = generate_identity_pack(aid, m, force=args.force)
        if results:
            print(f"  ✅ {aid}: {', '.join(results)}")
        else:
            print(f"  ⏭ {aid}: 已存在, 跳过")

    print(f"\n完成。OriginForce/agents/ 目录已更新。")


if __name__ == "__main__":
    main()

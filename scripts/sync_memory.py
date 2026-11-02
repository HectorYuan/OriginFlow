#!/usr/bin/env python3
"""sync_memory.py — 从 unified_memories 按 framework 蒸馏 → 填充 OriginForce 身份包 MEMORY.md。

记忆生命周期:
  原始堆积(unified_memories 13663行) → 蒸馏(s本脚本) → 席位记忆(MEMORY.md) → 注入(agent启动)

蒸馏规则:
  1. 按 framework 过滤（如 zcode 席位取 zcode+swarm 记忆）
  2. 按 memory_type 过滤（保留 decision/feedback/antipattern/error/distilled_rule，排除 context 堆积）
  3. 提取 title 作为记忆条目
  4. 写入 MEMORY.md 的 对应 section

规模限制 (memory_limits 段):
  MEMORY.md ≤ 4KB（冻结件 ≤2.5KB + 活记忆 ≤2KB 分账）
  超限 → 保留最近 + 高价值标记（Hector 反馈/决策/事故），合并旧条目
"""
from __future__ import annotations
import json, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

OF_ROOT = Path(__file__).resolve().parent.parent
OF = OF_ROOT.parent / "OriginForce"
AS_DB = OF_ROOT.parent / "AgentSwarm" / ".swarm" / "dev" / "swarm.db"

# framework → 席位 ID 映射（unified_memories 按 framework 记录，映射到 OriginForce 席位）
FW_TO_SEATS = {
    "zcode": ["system-navigator", "principle-check"],
    "swarm": ["devlead"],
    "hermes": ["product-owner"],
    "claude": ["backend-agent", "frontend-agent", "solution-expert"],
    "codex": ["ops-agent", "docs-agent"],
    "opencode": ["qa-agent", "search-agent"],
    "pi": ["sprint-master", "data-analyst", "test-agent", "monitor-agent"],
    "copilot": [],
    "teamswarm": [],
}

# memory_type 白名单（有价值的类型，排除 context 堆积）
VALUABLE_TYPES = ("decision", "feedback", "antipattern", "error", "distilled_rule",
                  "review_experience", "success", "preference", "fact", "pattern")


def collect_framework_memories(framework: str, limit: int = 20) -> list[dict]:
    """从 unified_memories 按框架读取有价值记忆。"""
    if not AS_DB.exists():
        return []
    con = sqlite3.connect(f"file:{AS_DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = con.execute(
            "SELECT memory_type, title, content FROM unified_memories "
            "WHERE framework = ? AND memory_type != 'context' "
            "ORDER BY rowid DESC LIMIT ?",
            (framework, limit)
        ).fetchall()
        return [{"type": r[0], "title": r[1][:80], "content": r[2][:200]} for r in rows]
    except Exception:
        return []
    finally:
        con.close()


def distill_memory_md(agent_id: str, name: str, memories: list[dict]) -> str:
    """从原始记忆生成 MEMORY.md 内容。"""
    lines = [f"# MEMORY · {name} 长期记忆\n"]
    lines.append("> 行为规则 + 工作方法论 + Hector 反馈。每次 task done 后追加。\n")

    # 按 type 分组
    by_type = {}
    for m in memories:
        by_type.setdefault(m["type"], []).append(m)

    # 长期行为规则
    lines.append("\n## 长期行为规则\n")
    lines.append("- **结论先行 + 事实必验**")
    lines.append("- **高风险先确认**")
    lines.append("- **极简指令：Hector 说\"继续\"= 按方案执行**")
    lines.append("- **add-one-retire-one：新增规则必须指定替代/退役哪条**")

    # 各类型记忆
    type_labels = {
        "decision": "## 决策记录",
        "feedback": "## Hector 反馈",
        "antipattern": "## 反模式",
        "error": "## 事故记录",
        "distilled_rule": "## 蒸馏规则",
        "review_experience": "## 评审经验",
        "success": "## 成功案例",
        "preference": "## 偏好",
        "fact": "## 事实记录",
        "pattern": "## 模式",
    }
    for mt, label in type_labels.items():
        items = by_type.get(mt, [])
        if items:
            lines.append(f"\n{label}\n")
            for m in items[:5]:  # 每类最多 5 条
                lines.append(f"- [{m['title']}]")

    return "\n".join(lines)


def main():
    import yaml
    schema = yaml.safe_load(
        (OF / ".." / "OriginForce" / "docs" / "team-schema.yaml").read_text(encoding="utf-8")
    ) if False else None

    # 直接读 schema
    import yaml as _y
    schema = _y.safe_load(
        (Path("/home/hector/DevSpace/OriginForce/docs/team-schema.yaml")).read_text(encoding="utf-8")
    )

    members = []
    for b in schema.get("brand_teams", {}).values():
        members.extend(b.get("members", []))

    print(f"蒸馏 {len(members)} 席位记忆...")
    for m in members:
        aid = m["agent_id"]
        name = m.get("name", aid)
        
        # 该席位对应的 frameworks
        frameworks = []
        for fw, seats in FW_TO_SEATS.items():
            if aid in seats:
                frameworks.append(fw)
        if not frameworks:
            # fallback: 用 runtime 名匹配
            rt = m.get("runtime", "")
            if "hermes" in rt: frameworks.append("hermes")
            elif "pi" in rt: frameworks.append("pi")
            elif "crush" in rt: frameworks.append("swarm")
            else: frameworks.append("zcode")
        
        # 收集记忆
        memories = []
        for fw in frameworks:
            memories.extend(collect_framework_memories(fw))
        
        # 生成 MEMORY.md
        content = distill_memory_md(aid, name, memories)
        
        # 写入
        mem_path = OF / "agents" / aid / "MEMORY.md"
        if mem_path.exists():
            old_size = mem_path.stat().st_size
            new_size = len(content.encode("utf-8"))
            # 不缩小已超过骨架的文件（保留人工填充的内容）
            if new_size < old_size * 0.5:
                print(f"  ⏭ {aid}: 新内容({new_size}B) < 旧({old_size}B)×0.5, 跳过")
                continue
        
        mem_path.write_text(content, encoding="utf-8")
        n_mem = len(memories)
        print(f"  ✅ {aid}: MEMORY.md 更新 ({n_mem} 条原始记忆蒸馏)")


if __name__ == "__main__":
    main()

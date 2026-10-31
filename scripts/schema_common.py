#!/usr/bin/env python3
"""schema 共享层 — check_team_drift.py 与 sync_team_schema.py 的单一逻辑源。

设计裁定 (architect 评审 2026-10-31, S2):
  - 检测器与生成器对「schema 怎么读、产物长什么样」必须零认知差, 本模块是唯一定义点
  - 产物幂等: 不含时间戳, 以 schema_content_hash 为版本键 (连跑两次零 diff)
  - 写地址权威 = runtime_bindings.as_definition (registered_in 降级为展示字段)
  - schema_content_hash 对「生成器消费的字段子集」做 canonical JSON sha256,
    注释/键序变化不触发假阳性
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

OF_ROOT = Path(__file__).resolve().parent.parent            # OriginFlow 仓根
ORIGINFORCE_ROOT = OF_ROOT.parent / "OriginForce"           # OriginForce 契约仓根 (sibling)
DEVSPACE_ROOT = OF_ROOT.parent
AS_ROOT = DEVSPACE_ROOT / "AgentSwarm"
ZS_ROOT = DEVSPACE_ROOT / "ZenSwarm"
ZCODE_HOME = Path.home() / ".zcode"
ZCODE_AGENTS = ZCODE_HOME / "agents"
ZCODE_CARDS = ZCODE_HOME / "agent-cards"
ROUTING_TABLE = ZCODE_HOME / "ROUTING_TABLE.md"
SCHEMA_PATH = ORIGINFORCE_ROOT / "docs" / "team-schema.yaml"
GENERATED_DIR = OF_ROOT / "docs" / "generated"
FEISHU_ROSTER = GENERATED_DIR / "feishu-roster.json"

REQUIRED_MEMBER_FIELDS = [
    "level", "capability_tier", "autonomy_scope", "runtime",
    "memory", "can_orchestrate", "registered_in", "team", "status",
]

# level-system.md §四 规范 token (L1=assist L2=execute L3=optimize L4=architect L5=decide)
LEVEL_TOKEN = {
    "L1": "l1_assist", "L2": "l2_execute", "L3": "l3_optimize",
    "L4": "l4_architect", "L5": "l5_decide",
}

# SCHEMA_OWNED_FIELDS: 生成器允许写入 AS definition frontmatter 的白名单。
# 绝不碰 metadata.role (schema.role 是描述句 ≠ AS slug) / metadata.type /
# persona* / skills / depends_on / 正文 / story_fuse_acceptance。
SCHEMA_OWNED_METADATA_FIELDS = [
    "level", "capability_tier", "autonomy_scope", "runtime", "memory",
    "can_orchestrate",
]

# ZS 身份键默认值 (裁定: zs_role 默认 engineer / reports_to 默认 brand_owner /
# soul 留空; runtime 键 status/current_session/current_task/started_at 永不动)
ZS_DEFAULT_ROLE = "engineer"
ZS_REPORTS_TO = "brand_owner"
ZS_RUNTIME_KEYS = ["status", "current_session", "current_task", "started_at"]

# capabilities 内置声明式映射表 (agent_id → capabilities);
# 未登记席位回落 ZS_DEFAULT_CAPABILITIES 并由调用方汇总 WARN
ZS_CAPABILITIES: dict[str, list[str]] = {
    "devlead": ["orchestrate", "review", "escalate"],
    "product-owner": ["decide", "roadmap", "report"],
    "architect-agent": ["design", "review", "adr"],
    "backend-agent": ["code", "test", "review"],
    "frontend-agent": ["code", "ui", "review"],
    "pm-agent": ["prd", "requirement", "prioritize"],
    "sprint-master": ["orchestrate", "schedule", "gate"],
    "qa-agent": ["review", "test", "lint"],
    "data-analyst": ["data", "sql", "report"],
    "search-agent": ["search", "context"],
    "test-agent": ["test", "e2e"],
    "monitor-agent": ["monitor", "alert"],
    "system-navigator": ["route"],
    "principle-check": ["audit"],
    "solution-expert": ["consult", "design", "proposal"],
}
ZS_DEFAULT_CAPABILITIES = ["code"]

LEVEL_ORDER = ["L5", "L4", "L3", "L2", "L1"]


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any] | None:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 解析失败由调用方决定如何报
        return None


def members_of(schema: dict[str, Any]) -> list[dict[str, Any]]:
    bt = (schema.get("brand_teams") or {}).get("brand:originforce") or {}
    return list(bt.get("members") or [])


def bindings_of(schema: dict[str, Any]) -> list[dict[str, Any]]:
    rb = schema.get("runtime_bindings") or {}
    return list(rb.get("bindings") or [])


def feishu_meta(schema: dict[str, Any]) -> dict[str, Any]:
    fm = schema.get("feishu_mapping") or {}
    keep = ("tenant", "brand", "lark_app_id", "base", "bindings", "sync_policies")
    return {k: fm[k] for k in keep if k in fm}


def binding_by_id(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["agent_id"]: b for b in bindings_of(schema) if b.get("agent_id")}


def _workspace_path(rel: str) -> Path:
    """runtime_bindings 里的仓相对路径 (AgentSwarm/... 或 ZenSwarm/...) → 绝对路径。"""
    return DEVSPACE_ROOT / rel


def canonical_view(schema: dict[str, Any]) -> dict[str, Any]:
    """生成器消费的字段子集 — hash 与产物只依赖这里。"""
    return {
        "members": members_of(schema),
        "runtime_bindings": bindings_of(schema),
        "feishu_mapping": feishu_meta(schema),
    }


def schema_content_hash(schema: dict[str, Any]) -> str:
    payload = json.dumps(
        canonical_view(schema), sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def derive_description(member: dict[str, Any]) -> str:
    return f"{member.get('name', '')} — {member.get('role', '')}"


def capabilities_for(agent_id: str) -> list[str]:
    return ZS_CAPABILITIES.get(agent_id, ZS_DEFAULT_CAPABILITIES)


def render_agent_card(
    member: dict[str, Any], binding: dict[str, Any], schema_hash: str
) -> dict[str, Any]:
    """zcode A2A 卡 (方案 §3.4: description/skills 从 schema 派生)。"""
    agent_id = member["agent_id"]
    return {
        "agent_id": agent_id,
        "name": member.get("name", ""),
        "description": derive_description(member),
        "level": member.get("level", ""),
        "capability_tier": member.get("capability_tier", ""),
        "autonomy_scope": member.get("autonomy_scope", ""),
        "runtime": member.get("runtime", ""),
        "role": member.get("role", ""),
        "skills": capabilities_for(agent_id),
        "team": member.get("team", ""),
        "status": member.get("status", ""),
        "runtime_bindings": binding,
        "generated_from": {
            "source": "OriginForce/docs/team-schema.yaml",
            "schema_content_hash": schema_hash,
        },
    }


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_feishu_roster(
    schema: dict[str, Any], members: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """飞书 roster 全量镜像: schema 事实 + tenant 元数据, 无 chat_id (S1.5 回填位)。

    members=None 时取全量; 生成器传入 P0 校验通过的有效成员 (P0 缺字段成员跳过投影)。
    """
    roster = []
    for m in (members if members is not None else members_of(schema)):
        roster.append({
            k: m.get(k, "")
            for k in ("agent_id", "name", "level", "capability_tier",
                      "autonomy_scope", "runtime", "role", "team", "status")
        })
    return {
        "generated_from": {
            "source": "OriginForce/docs/team-schema.yaml",
            "schema_content_hash": schema_content_hash(schema),
        },
        "tenant": feishu_meta(schema),
        "roster": roster,
    }


def render_roster_markdown(
    schema: dict[str, Any], members: list[dict[str, Any]] | None = None
) -> str:
    """路由表标记段名册: 按级别×能力档分组的席位索引 (只写标记内, 手写表不动)。"""
    schema_hash = schema_content_hash(schema)
    groups: dict[str, list[dict[str, Any]]] = {}
    for m in (members if members is not None else members_of(schema)):
        groups.setdefault(str(m.get("level", "?")), []).append(m)
    lines = [
        f"<!-- BEGIN generated:roster "
        f"(source: OriginForce/docs/team-schema.yaml; "
        f"schema_content_hash={schema_hash}; machine-managed, do-not-edit) -->",
        "",
        "> 席位索引由 sync_team_schema.py 按 schema 生成; 手写路由表见上方各节。",
        "",
    ]
    for lvl in LEVEL_ORDER:
        ms = groups.pop(lvl, None)
        if not ms:
            continue
        tier = ms[0].get("capability_tier", "?")
        lines.append(f"### {lvl} · {tier}")
        for m in sorted(ms, key=lambda x: x["agent_id"]):
            lines.append(f"- {m['agent_id']} — {m.get('role', '')}")
        lines.append("")
    for leftover in sorted(groups):
        for m in sorted(groups[leftover], key=lambda x: x["agent_id"]):
            lines.append(f"- {m['agent_id']} — {m.get('role', '')}")
        lines.append("")
    lines.append("<!-- END generated:roster -->")
    return "\n".join(lines) + "\n"


def upsert_generated_segment(text: str, segment: str) -> str:
    """在文本中替换 BEGIN/END 标记段; 无标记段则追加到文末。手写内容永不改写。"""
    import re

    pat = re.compile(
        r"<!-- BEGIN generated:roster\b.*?<!-- END generated:roster -->\n?",
        re.S,
    )
    if pat.search(text):
        return pat.sub(segment.rstrip("\n") + "\n", text)
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + segment

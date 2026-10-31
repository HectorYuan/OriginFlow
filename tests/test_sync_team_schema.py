"""sync_team_schema.py / schema_common.py / check_team_drift.py S2 单测。

覆盖 (devlead 验收要求):
  1. 幂等双跑零 diff
  2. P0 缺字段拒投影
  3. dev.toml 豁免
  4. hash 陈旧检测
  5. 外科手术绝不碰 metadata.role / 正文 / story_fuse_acceptance
  6. ZS merge 保留 runtime 键与自定义键
  7. 路由表 upsert 不动手写内容
  8. 禁写清单前缀校验
测试全部走 tmp_path, 不触碰真实仓库与 ~/.zcode。
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import check_team_drift as drift
import schema_common as sc
import sync_team_schema as sync


def make_member(aid: str = "backend-agent", **kw) -> dict:
    base = {
        "agent_id": aid, "name": "测试员", "level": "L3",
        "capability_tier": "specialist", "autonomy_scope": "project",
        "runtime": "claude-code", "memory": "task",
        "can_orchestrate": ["L1", "L2"],
        "registered_in": f"AgentSwarm/agents/definitions/{aid}.md",
        "role": "测试角色", "team": "brand:originforce", "status": "active",
    }
    base.update(kw)
    return base


def make_binding(aid: str = "backend-agent") -> dict:
    return {
        "agent_id": aid,
        "as_definition": f"AgentSwarm/agents/definitions/{aid}.md",
        "zs_agent_toml": f"ZenSwarm/.team/agents/{aid}.toml",
        "herdr_pane_title": f"{aid} @ <task>",
        "zcode_subagent": aid,
        "zcode_agent_card": f"~/.zcode/agent-cards/{aid}.json",
        "feishu": "see feishu_mapping.bindings",
    }


def make_schema(members=None, bindings=None) -> dict:
    return {
        "brand_teams": {
            "brand:originforce": {"members": members if members is not None else [make_member()]}
        },
        "runtime_bindings": {"bindings": bindings if bindings is not None else [make_binding()]},
        "feishu_mapping": {"tenant": "指南宇宙", "brand": "源力觉醒 (SourceForce)", "bindings": []},
    }


def tmp_roots(tmp_path: Path) -> sync.Roots:
    roots = sync.Roots(
        as_root=tmp_path / "AgentSwarm",
        zs_root=tmp_path / "ZenSwarm",
        zcode_cards=tmp_path / "zcode" / "agent-cards",
        routing_table=tmp_path / ".zcode" / "ROUTING_TABLE.md",
        generated_dir=tmp_path / "OF" / "docs" / "generated",
    )
    # 生成器不凭空创建路由表, 预置手写内容模拟真实环境
    roots.routing_table.parent.mkdir(parents=True, exist_ok=True)
    roots.routing_table.write_text(
        "# 子智能体路由表\n\n## 按任务类型\n\n| 手写 | 表 |\n\n",
        encoding="utf-8",
    )
    return roots


def apply_ops(plan: sync.Plan) -> None:
    for op in plan.ops:
        op.path.parent.mkdir(parents=True, exist_ok=True)
        op.path.write_text(op.new, encoding="utf-8")


DEFINITION_TEXT = """---
name: backend-agent
description: 后端开发 Agent — 既有描述
metadata:
  level: l2_execute
  role: backend
  type: executor
  capability_tier: specialist
  autonomy_scope: project
  runtime: claude-code
  memory: task
  can_orchestrate: [l1, l2]
---

# Backend Agent 正文

人设与职责说明。

## 经历

- 正文段落

<!-- story_fuse_acceptance: experience-v1 -->
"""


def seed_definition(tmp_path: Path, text: str = DEFINITION_TEXT,
                    aid: str = "backend-agent") -> Path:
    p = tmp_path / "AgentSwarm" / "agents" / "definitions" / f"{aid}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ---------- 1. 幂等双跑零 diff ----------


def test_idempotent_two_runs_zero_diff(tmp_path):
    seed_definition(tmp_path)
    roots = tmp_roots(tmp_path)
    schema = make_schema()

    plan1 = sync.build_plan(schema, roots)
    assert plan1.errors == []
    apply_ops(plan1)
    assert plan1.ops, "首跑必须有产物"

    plan2 = sync.build_plan(schema, roots)
    assert plan2.ops == [], "第二次 build 必须零 diff"
    assert plan2.errors == []


def test_idempotent_check_mode(tmp_path):
    seed_definition(tmp_path)
    roots = tmp_roots(tmp_path)
    schema = make_schema()
    apply_ops(sync.build_plan(schema, roots))
    plan = sync.build_plan(schema, roots)
    assert plan.ops == []  # --check 模拟: 无待变更


# ---------- 2. P0 缺字段拒投影 ----------


def test_p0_missing_field_skips_all_projections(tmp_path):
    seed_definition(tmp_path)
    roots = tmp_roots(tmp_path)
    bad = make_member("broken-agent", level=None)
    del bad["level"]
    schema = make_schema(
        members=[make_member(), bad],
        bindings=[make_binding(), make_binding("broken-agent")],
    )
    plan = sync.build_plan(schema, roots)
    assert any("P0" in e and "broken-agent" in e for e in plan.errors)
    aid_ops = [op for op in plan.ops if "broken-agent" in str(op.path)]
    assert aid_ops == [], "P0 成员不得有任何投影"
    # 有效成员照常投影
    assert any(op.label.startswith("ZS toml backend-agent") for op in plan.ops)


def test_p0_member_excluded_from_roster_and_feishu(tmp_path):
    roots = tmp_roots(tmp_path)
    bad = make_member("broken-agent")
    del bad["memory"]
    schema = make_schema(
        members=[make_member(), bad],
        bindings=[make_binding(), make_binding("broken-agent")],
    )
    plan = sync.build_plan(schema, roots)
    apply_ops(plan)
    roster = json.loads(
        (roots.generated_dir / "feishu-roster.json").read_text(encoding="utf-8"))
    ids = [r["agent_id"] for r in roster["roster"]]
    assert ids == ["backend-agent"]
    routing = roots.routing_table.read_text(encoding="utf-8")
    assert "broken-agent" not in routing


def test_p0_missing_binding(tmp_path):
    roots = tmp_roots(tmp_path)
    schema = make_schema(members=[make_member()], bindings=[])
    plan = sync.build_plan(schema, roots)
    assert any("缺 runtime_binding" in e for e in plan.errors)


# ---------- 3. dev.toml 豁免 ----------


def test_dev_toml_exempt_in_bindings_integrity(tmp_path, monkeypatch):
    zs_root = tmp_path / "ZenSwarm"
    agents_dir = zs_root / ".team" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "dev.toml").write_text('id = "dev"\n', encoding="utf-8")
    (agents_dir / "mystery.toml").write_text('id = "mystery"\n', encoding="utf-8")
    monkeypatch.setattr(drift, "ZS_ROOT", zs_root)
    drift.ERRORS.clear()
    drift.WARNS.clear()
    members = [make_member()]
    bindings = [make_binding()]
    drift.check_bindings_integrity(members, bindings)
    assert not any("dev.toml" in w for w in drift.WARNS), "dev.toml 必须豁免"
    assert any("mystery.toml" in w for w in drift.WARNS)


def test_dev_toml_never_written(tmp_path):
    roots = tmp_roots(tmp_path)
    dev = roots.zs_root / ".team" / "agents" / "dev.toml"
    dev.parent.mkdir(parents=True, exist_ok=True)
    dev.write_text('id = "dev"\nrole = "engineer"\n', encoding="utf-8")
    schema = make_schema()
    plan = sync.build_plan(schema, roots)
    assert all(op.path != dev for op in plan.ops)
    assert dev.read_text(encoding="utf-8") == 'id = "dev"\nrole = "engineer"\n'


def test_forbidden_prefix_dev_toml():
    reason = sync.forbidden_reason(sc.ZS_ROOT / ".team" / "agents" / "dev.toml")
    assert reason is not None
    assert sync.forbidden_reason(
        sc.ZS_ROOT / ".team" / "agents" / "backend-agent.toml") is None


# ---------- 4. hash 陈旧检测 ----------


def test_stale_card_hash_detected(tmp_path, monkeypatch):
    cards = tmp_path / "zcode" / "agent-cards"
    cards.mkdir(parents=True)
    schema = make_schema()
    good_hash = sc.schema_content_hash(schema)
    (cards / "backend-agent.json").write_text(json.dumps({
        "agent_id": "backend-agent",
        "generated_from": {"schema_content_hash": "deadbeef00000000"},
    }), encoding="utf-8")
    monkeypatch.setattr(drift, "ZCODE_CARDS", cards)
    drift.ERRORS.clear()
    drift.WARNS.clear()
    drift.check_zcode_cards(schema, [make_binding()])
    assert any("陈旧" in e for e in drift.ERRORS)

    (cards / "backend-agent.json").write_text(json.dumps({
        "agent_id": "backend-agent",
        "generated_from": {"schema_content_hash": good_hash},
    }), encoding="utf-8")
    drift.ERRORS.clear()
    drift.check_zcode_cards(schema, [make_binding()])
    assert drift.ERRORS == []


def test_stale_routing_segment_detected(tmp_path, monkeypatch):
    schema = make_schema()
    stale = "<!-- BEGIN generated:roster (stale) -->\nold\n<!-- END generated:roster -->\n"
    routing = tmp_path / ".zcode" / "ROUTING_TABLE.md"
    routing.parent.mkdir(parents=True, exist_ok=True)
    routing.write_text("# 路由表\n\n" + stale, encoding="utf-8")
    monkeypatch.setattr(drift, "ROUTING_TABLE", routing)
    drift.ERRORS.clear()
    drift.check_routing_table(schema)
    assert any("不一致" in e for e in drift.ERRORS)


# ---------- 5. 外科手术边界 ----------


def test_syringe_never_touches_role_body_acceptance(tmp_path):
    seed_definition(tmp_path)
    roots = tmp_roots(tmp_path)
    schema = make_schema()
    plan = sync.build_plan(schema, roots)
    apply_ops(plan)
    out = (roots.as_root / "agents" / "definitions" / "backend-agent.md").read_text(
        encoding="utf-8")
    assert "role: backend" in out, "metadata.role (AS slug) 绝不被改写"
    assert "role: 测试角色" not in out, "schema.role 描述句不得写进 metadata.role"
    assert "# Backend Agent 正文" in out
    assert "- 正文段落" in out
    assert "<!-- story_fuse_acceptance: experience-v1 -->" in out
    assert "level: l3_optimize" in out, "level 应升级为 schema L3 对应 token"


def test_syringe_can_orchestrate_block_to_inline(tmp_path):
    text = DEFINITION_TEXT.replace(
        "  can_orchestrate: [l1, l2]",
        "  can_orchestrate:\n    - l1\n    - l2",
    )
    new, changes = sync.patch_definition_text(text, make_member())
    meta = sc.yaml.safe_load(new.split("---")[1])
    assert meta["metadata"]["can_orchestrate"] == ["l1", "l2"]
    assert "    - l1" not in new


def test_syringe_skeleton_when_missing(tmp_path):
    roots = tmp_roots(tmp_path)
    schema = make_schema()
    plan = sync.build_plan(schema, roots)
    op = next(op for op in plan.ops if "skeleton" in op.label)
    assert op.old is None
    apply_ops(plan)
    text = op.path.read_text(encoding="utf-8")
    meta = sc.yaml.safe_load(text.split("---")[1])
    assert meta["name"] == "backend-agent"
    assert meta["metadata"]["level"] == "l3_optimize"


def test_syringe_deviation_skip(tmp_path):
    seed_definition(tmp_path)
    m = make_member("solution-expert", runtime="pi")
    b = make_binding("solution-expert")
    roots = tmp_roots(tmp_path)
    seed_definition(tmp_path, aid="solution-expert")
    schema = make_schema(members=[m], bindings=[b])
    plan = sync.build_plan(schema, roots)
    as_op = next(op for op in plan.ops if op.label.startswith("AS definition"))
    assert "runtime" not in as_op.new or "runtime: claude-code" in as_op.new


# ---------- 6. ZS merge ----------


def test_zs_merge_preserves_runtime_and_custom_keys():
    existing = tomllib.loads(
        'id = "backend-agent"\nrole = "engineer"\nreports_to = "someone"\n'
        'soul = "~/.zenswarm/agents/backend-agent/soul.md"\n'
        'capabilities = ["code"]\nstatus = "active"\ncurrent_session = "s1"\n'
        'current_task = "T-1"\nstarted_at = 42\ncustom_key = "keep-me"\n')
    text, warns = sync.zs_toml_text(make_member(), existing)
    data = tomllib.loads(text)
    assert data["status"] == "active"
    assert data["current_task"] == "T-1"
    assert data["started_at"] == 42
    assert data["custom_key"] == "keep-me"
    # P2 脏值 (旧简化版遗留 soul 路径): 净化置空 + WARN, 键保留
    assert data["soul"] == ""
    assert any("soul" in w for w in warns)
    assert data["reports_to"] == sync.ZS_REPORTS_TO  # 身份键被 schema 权威覆盖
    assert data["capabilities"] == ["code", "test", "review"]


def test_zs_custom_key_dirty_value_skipped():
    existing = tomllib.loads(
        'id = "backend-agent"\nstatus = "idle"\ncustom = "~/.some/path"\n')
    text, warns = sync.zs_toml_text(make_member(), existing)
    data = tomllib.loads(text)
    assert "custom" not in data, "不安全自定义键跳过, 不写脏值"
    assert any("custom" in w for w in warns)
    assert data["status"] == "idle"


def test_zs_toml_text_never_raises():
    _text, _warns = sync.zs_toml_text(make_member(), {"soul": "~x", "odd": "~y"})
    _text2, _warns2 = sync.zs_toml_text(make_member(), None)


def test_zs_new_file_soul_empty():
    text, _warns = sync.zs_toml_text(make_member(), None)
    data = tomllib.loads(text)
    assert data["soul"] == ""
    assert data["status"] == "idle"
    assert data["role"] == sync.ZS_DEFAULT_ROLE


def test_zs_bindings_existence_check(tmp_path, monkeypatch):
    zs_root = tmp_path / "ZenSwarm"
    monkeypatch.setattr(drift, "ZS_ROOT", zs_root)
    drift.ERRORS.clear()
    drift.check_zs_bindings([make_binding()])
    assert any("缺失" in e for e in drift.ERRORS)
    p = zs_root / ".team" / "agents" / "backend-agent.toml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('id = "other-agent"\n', encoding="utf-8")
    drift.ERRORS.clear()
    drift.check_zs_bindings([make_binding()])
    assert any("id=" in e for e in drift.ERRORS), "id != agent_id 必须报"
    assert any("缺身份键" in e for e in drift.ERRORS)


# ---------- 7. 路由表 upsert ----------


def test_routing_upsert_keeps_handwritten():
    handwritten = "# 子智能体路由表\n\n## 按任务类型\n\n| 手写 | 表 |\n"
    old_seg = ("<!-- BEGIN generated:roster (old) -->\n- stale\n"
               "<!-- END generated:roster -->\n")
    text = handwritten + "\n" + old_seg
    new_seg = sc.render_roster_markdown(make_schema())
    out = sc.upsert_generated_segment(text, new_seg)
    assert "## 按任务类型" in out
    assert "| 手写 | 表 |" in out
    assert "BEGIN generated:roster" in out
    assert out.count("BEGIN generated:roster") == 1
    assert "stale" not in out


def test_routing_append_when_no_segment():
    text = "# 路由表\n\n手写内容\n"
    seg = sc.render_roster_markdown(make_schema())
    out = sc.upsert_generated_segment(text, seg)
    assert out.startswith("# 路由表")
    assert "BEGIN generated:roster" in out


# ---------- 8. 禁写清单 ----------


def test_forbidden_prefixes():
    assert sync.forbidden_reason(sc.AS_ROOT / "specs" / "x.md") is not None
    assert sync.forbidden_reason(sc.AS_ROOT / "team" / "teams.yaml") is not None
    assert sync.forbidden_reason(sc.AS_ROOT / "memory" / "x.md") is not None
    assert sync.forbidden_reason(sc.ZCODE_HOME / "agents" / "backend-agent.md") is not None
    assert sync.forbidden_reason(sc.ZCODE_HOME / "CLAUDE.md") is not None
    assert sync.forbidden_reason(sc.ZCODE_HOME / "settings.json") is not None
    assert sync.forbidden_reason(sc.ORIGINFORCE_ROOT / "docs" / "team-schema.yaml") is not None
    assert sync.forbidden_reason(sc.ORIGINFORCE_ROOT / "agents" / "solution-expert" / "IDENTITY.md") is not None
    assert sync.forbidden_reason(sc.ORIGINFORCE_ROOT / "docs" / "team-roster.md") is not None
    # 合法写地址
    assert sync.forbidden_reason(sc.AS_ROOT / "agents" / "definitions" / "backend-agent.md") is None
    assert sync.forbidden_reason(sc.ZCODE_HOME / "agent-cards" / "x.json") is None
    assert sync.forbidden_reason(sc.OF_ROOT / "docs" / "generated" / "feishu-roster.json") is None


# ---------- 卡与共享层 ----------


def test_agent_card_contains_bindings_and_hash():
    schema = make_schema()
    b = make_binding()
    card = sc.render_agent_card(make_member(), b, sc.schema_content_hash(schema))
    assert card["runtime_bindings"] == b
    assert card["generated_from"]["schema_content_hash"] == sc.schema_content_hash(schema)
    assert card["skills"] == ["code", "test", "review"]


def test_schema_hash_stable_across_comment_noise():
    s1 = make_schema()
    s2 = make_schema()
    s2["new_top_key"] = "注释性内容不影响 hash"
    assert sc.schema_content_hash(s1) == sc.schema_content_hash(s2)
    s3 = make_schema(members=[make_member(role="改动角色")])
    assert sc.schema_content_hash(s1) != sc.schema_content_hash(s3)


def test_feishu_roster_shape():
    schema = make_schema()
    roster = sc.render_feishu_roster(schema)
    assert roster["tenant"]["tenant"] == "指南宇宙"
    assert roster["roster"][0]["agent_id"] == "backend-agent"
    assert roster["generated_from"]["schema_content_hash"]

#!/usr/bin/env python3
"""OriginForce 团队漂移检测 — docs/team-schema.yaml drift_detection.cron_6h 的实现。

比对源（schema drift_detection.sources + 2026-10-20 实证过的漂移类别 + S2 五域投影）:
  1. schema 自身 YAML 语法 + required_member_fields 必填
  2. members[].agent_id → ~/.zcode/agents/<id>.md 注册存在性
  3. members 双轨字段 ↔ AgentSwarm/specs/level-system.md §2.3 默认值表
  4. members ↔ AgentSwarm/agents/definitions/<id>.md metadata（写地址权威 = runtime_bindings.as_definition）
  5. members(交集) ↔ AgentSwarm/team/teams.yaml permission_level
  6. TOOLS.md 委派表 ↔ docs/team-roster.md 协作队友表（集合相等）
  7. 过渡 token 残留: AgentSwarm skills/ + agents/definitions/ + loader/ 中的 l3_advise
  S2 增补（生成器 sync_team_schema.py 的验收面，红先于绿）:
  8. ZS binding: ZenSwarm/.team/agents/<id>.toml 存在性 + id==agent_id + 身份键齐全（dev.toml 豁免）
  9. zcode cards: ~/.zcode/agent-cards/<id>.json 存在性 + JSON 可解析 + schema_content_hash 一致
 10. 路由表: generated:roster 标记段存在性 + 与 schema 渲染一致
 11. runtime_bindings 完整性: 成员↔binding 一一对应 + as_definition 存在 + 各域寻址键自洽
 12. feishu roster: docs/generated/feishu-roster.json 存在性 + hash 一致（hook，告警推送 S4 接线）

退出码: 0 = 无 ERROR 级漂移; 1 = 有（WARN 不影响退出码）。
允许偏差: DEVIATIONS 登记且 schema 内有同源注释的差异不报 ERROR。
产物格式唯一定义点: scripts/schema_common.py（检测器与生成器共享，防两处逻辑漂移）。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_projection_guard import guard_routing_segment  # noqa: E402 — 单源守卫判据
from schema_common import (  # noqa: E402
    AS_ROOT,
    FEISHU_ROSTER,
    LEVEL_TOKEN,
    OF_ROOT,
    ORIGINFORCE_ROOT,
    REQUIRED_MEMBER_FIELDS,
    ROUTING_TABLE,
    SCHEMA_PATH,
    ZCODE_AGENTS,
    ZCODE_CARDS,
    ZS_ROOT,
    bindings_of,
    load_schema,
    render_roster_markdown,
    schema_content_hash,
)

SPEC_TOKEN = LEVEL_TOKEN

# (agent_id, field) → 理由；schema 内有同源行内注释，不报 ERROR
DEVIATIONS = {
    ("solution-expert", "runtime"):
        "设计承载 pi（herdr 第三阶段）；spec 当前承载 claude-code（schema 行内注释在案）",
    # S1 清账 20261031: devlead can_orchestrate 含 l5 —— schema v2.0 裁定
    # (product-owner 同为 L5 决策档互审; definitions 已对齐)。规范表 L4 行为
    # 其余 L4 席位默认, devlead 为登记例外。
    ("devlead", "can_orchestrate"):
        "devlead 例外含 l5 —— schema v2.0 裁定 (PO 同级互审), definitions 已对齐",
    # S1.5 20261031: 5 席位 runtime=hermes 为运行真相 (definitions 自 10-19 即
    # hermes, 47h 生产运行), schema v2.0 已对齐 hermes; 规范表默认 claude-code
    # 为 L1/L2 新席位基线, 既有席位按运行事实登记偏差。
    ("data-analyst", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("search-agent", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("test-agent", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("monitor-agent", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("system-navigator", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("docs-agent", "runtime"): "运行真相 hermes (definitions 10-19 起), schema 已对齐",
    ("ceo", "runtime"): "CEO 用 hermes 运行时（Hector 指定），非 claude-code 默认",
}



ERRORS: list[str] = []
WARNS: list[str] = []

# 第 13 类: 席位 MEMORY.md 体量阈值 (写入模块常量便于未来调)
MEMORY_WARN_BYTES = 3072
MEMORY_ERR_BYTES = 5120


def err(msg: str) -> None:
    ERRORS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 解析失败本身就是漂移
        err(f"YAML 解析失败 {path}: {e}")
        return None


def ci_eq(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return [str(x).lower() for x in a] == [str(x).lower() for x in b]
    return str(a).lower() == str(b).lower()


def check_schema_basic(schema: dict) -> list[dict]:
    for key in ("brand_teams", "planned_roster", "protocol_stack", "drift_detection"):
        if key not in schema:
            err(f"schema 缺少顶层键: {key}")
    members = (
        schema.get("brand_teams", {}).get("brand:originforce", {}).get("members") or []
    )
    for m in members:
        for f in REQUIRED_MEMBER_FIELDS:
            if f not in m:
                err(f"成员 {m.get('agent_id', '?')} 缺必填字段 {f}")
    return members


def check_zcode_registration(members: list[dict]) -> None:
    for m in members:
        f = ZCODE_AGENTS / f"{m['agent_id']}.md"
        if not f.exists():
            err(f"ZCode 注册缺失: {f}（成员 {m['agent_id']}）")


def parse_spec_defaults() -> dict[str, dict]:
    """解析 level-system.md §2.3 默认值表 → {L3: {field: value}}。"""
    spec = AS_ROOT / "specs" / "level-system.md"
    if not spec.exists():
        err(f"规范文件缺失: {spec}")
        return {}
    defaults: dict[str, dict] = {}
    for line in spec.read_text(encoding="utf-8").splitlines():
        mm = re.match(r"^\|\s*(L[1-5])\s*\|(.+)\|\s*$", line)
        if not mm:
            continue
        cells = [c.strip() for c in mm.group(2).split("|")]
        if len(cells) != 5 or mm.group(1) in defaults:
            continue
        defaults[mm.group(1)] = dict(
            zip(
                ["capability_tier", "autonomy_scope", "runtime", "memory",
                 "can_orchestrate"],
                cells,
            )
        )
    if len(defaults) < 5:
        err(f"level-system.md §2.3 默认值表解析不完整（仅 {len(defaults)}/5 行）")
    return defaults


def norm_spec(want: str):
    """规范表单元格 → 可比较值: '[l1, l2]'→list; '-'/'-'→None(跳过); 其余→lower str。"""
    if isinstance(want, str) and want.startswith("["):
        return [x.strip().lower() for x in want.strip("[]").split(",") if x.strip()]
    if want in ("-", "", None):
        return None
    return str(want).lower()


def check_vs_spec(members: list[dict], defaults: dict[str, dict]) -> None:
    for m in members:
        lvl = str(m.get("level", ""))
        exp = defaults.get(lvl)
        if exp is None:
            if lvl.upper() in SPEC_TOKEN:
                continue  # 大写 Lx 按测试口径合法（test_uppercase_still_passes）
            err(f"{m['agent_id']}: level '{lvl}' 不在 L1-L5 规范")
            continue
        for field, raw in exp.items():
            want = norm_spec(raw)
            if want is None:
                continue
            if (m["agent_id"], field) in DEVIATIONS:
                continue  # 已登记偏差（schema 行内注释在案）
            got = m.get(field)
            if got is None:
                err(f"{m['agent_id']}.{field}: schema 缺失（规范默认 {want}）")
            elif not ci_eq(got, want):
                err(
                    f"{m['agent_id']}.{field}: schema={got} ≠ 规范默认 {want}"
                    f"（level-system.md §2.3 {lvl} 行）"
                )


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:  # noqa: BLE001
        err(f"definition frontmatter 解析失败: {path}")
        return {}


def check_definitions(members: list[dict], bindings: list[dict]) -> None:
    """S2 起: 写地址权威 = runtime_bindings.as_definition（registered_in 降级为展示字段）。

    由此补上 registered_in 指向非 definitions 目录的成员（如 solution-expert
    身份包）的检查空洞。比对字段 = SCHEMA_OWNED_METADATA_FIELDS 白名单。
    """
    by_id = {b.get("agent_id"): b for b in bindings if b.get("agent_id")}
    for m in members:
        b = by_id.get(m["agent_id"])
        if b is None:
            continue  # 对应缺失由 check_bindings_integrity 报
        rel = str(b.get("as_definition", ""))
        if not rel.startswith("AgentSwarm/"):
            continue  # 非 AS definitions 寻址由 check_bindings_integrity 报
        path = AS_ROOT / rel.removeprefix("AgentSwarm/")
        if not path.exists():
            err(f"definition 缺失: {path}（成员 {m['agent_id']}）")
            continue
        meta = (parse_frontmatter(path).get("metadata")) or {}
        for field in ("level", "capability_tier", "autonomy_scope", "memory",
                      "can_orchestrate", "runtime"):
            if field not in meta:
                err(
                    f"{m['agent_id']}: definition metadata.{field} 缺失"
                    f"（schema 权威字段，sync_team_schema.py 应补齐）"
                )
        lvl = str(m.get("level", "")).upper()
        want_level = SPEC_TOKEN.get(lvl, str(m.get("level", "")).lower())
        got_level = str(meta.get("level", "")).lower()
        if got_level and got_level not in (want_level, lvl.lower()):
            err(
                f"{m['agent_id']}: definition level={meta.get('level')} "
                f"≠ schema {m['level']}（规范 token {want_level}）"
            )
        for field in ("capability_tier", "autonomy_scope", "memory"):
            if field in meta and not ci_eq(meta[field], m.get(field, "")):
                err(
                    f"{m['agent_id']}: definition {field}={meta[field]} "
                    f"≠ schema {m.get(field)}"
                )
        if "can_orchestrate" in meta and (m["agent_id"], "can_orchestrate") not in DEVIATIONS:
            if not ci_eq(meta["can_orchestrate"], m.get("can_orchestrate")):
                err(
                    f"{m['agent_id']}: definition can_orchestrate="
                    f"{meta['can_orchestrate']} ≠ schema {m.get('can_orchestrate')}"
                )
        if "runtime" in meta and (m["agent_id"], "runtime") not in DEVIATIONS:
            if not ci_eq(meta["runtime"], m.get("runtime", "")):
                err(
                    f"{m['agent_id']}: definition runtime={meta['runtime']} "
                    f"≠ schema {m.get('runtime')}"
                )


def check_teams_yaml(members: list[dict]) -> None:
    path = AS_ROOT / "team" / "teams.yaml"
    if not path.exists():
        err(f"比对源缺失: {path}")
        return
    data = load_yaml(path) or {}
    by_id: dict[str, str] = {}
    for team in (data.get("teams") or {}).values():
        for tm in team.get("members") or []:
            by_id[tm.get("agent_id", "")] = str(tm.get("permission_level", ""))
    for m in members:
        other = by_id.get(m["agent_id"])
        if other and other.upper() != str(m.get("level", "")).upper():
            err(
                f"{m['agent_id']}: teams.yaml permission_level={other} "
                f"≠ schema level={m.get('level')}"
            )


def extract_backtick_col(path: Path, header_prefix: str) -> set[str]:
    """取指定 ## 小节内表格第 2 列的 `code` 值集合。"""
    names: set[str] = set()
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.startswith(header_prefix)
            continue
        if in_section and line.startswith("|") and "`" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                mm = re.fullmatch(r"`([A-Za-z0-9_-]+)`", cells[1])
                if mm:
                    names.add(mm.group(1))
    return names


def check_tools_vs_roster() -> None:
    tools = ORIGINFORCE_ROOT / "agents" / "solution-expert" / "TOOLS.md"
    roster = ORIGINFORCE_ROOT / "docs" / "team-roster.md"
    for p in (tools, roster):
        if not p.exists():
            err(f"比对源缺失: {p}")
            return
    t = extract_backtick_col(tools, "## 委派队友")
    r = extract_backtick_col(roster, "## 协作队友")
    if not t:
        err("TOOLS.md 委派队友表解析为空")
    if not r:
        err("team-roster.md 协作队友表解析为空")
    if t and r and t != r:
        for x in sorted(t - r):
            err(f"TOOLS.md 有而 team-roster.md 无: {x}")
        for x in sorted(r - t):
            err(f"team-roster.md 有而 TOOLS.md 无: {x}")


def check_residue() -> None:
    patterns = [
        AS_ROOT / "skills",
        AS_ROOT / "agents" / "definitions",
        AS_ROOT / "loader",
    ]
    for root in patterns:
        if not root.exists():
            warn(f"残留扫描目录缺失（跳过）: {root}")
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix not in (".md", ".yaml", ".yml", ".py"):
                continue
            try:
                if re.search(r"\bl3_advise\b", p.read_text(encoding="utf-8")):
                    err(f"过渡 token l3_advise 残留: {p}")
            except (OSError, UnicodeDecodeError):
                continue


def check_zs_bindings(bindings: list[dict]) -> None:
    """S2-⑧ ZS binding: .team/agents/<id>.toml 存在性 + id==agent_id + 身份键齐全。

    身份键 = id/role/reports_to/soul/capabilities（生成器权威）；runtime 键
    （status/current_session/current_task/started_at）不在此检查范围。
    """
    for b in bindings:
        aid = b.get("agent_id", "?")
        rel = str(b.get("zs_agent_toml", ""))
        if not rel.startswith("ZenSwarm/"):
            err(f"{aid}: zs_agent_toml 未指向 ZenSwarm 仓: {rel!r}")
            continue
        p = ZS_ROOT / rel.removeprefix("ZenSwarm/")
        if not p.exists():
            err(f"ZS agent toml 缺失: {p}（成员 {aid}）")
            continue
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            err(f"ZS toml 解析失败 {p}: {e}")
            continue
        if data.get("id") != aid:
            err(f"ZS toml id={data.get('id')!r} ≠ agent_id {aid!r}（{p}）")
        for k in ("id", "role", "reports_to", "soul", "capabilities"):
            if k not in data:
                err(f"ZS toml 缺身份键 {k}: {p}")
        caps = data.get("capabilities")
        if caps is not None and not isinstance(caps, list):
            err(f"ZS toml capabilities 非 list: {p}")


def check_zcode_cards(schema: dict, bindings: list[dict]) -> None:
    """S2-⑨ zcode cards: 存在性 + JSON 可解析 + schema_content_hash 一致（陈旧卡检测）。"""
    h = schema_content_hash(schema)
    for b in bindings:
        aid = b.get("agent_id", "?")
        p = ZCODE_CARDS / f"{aid}.json"
        if not p.exists():
            err(f"zcode agent card 缺失: {p}（成员 {aid}）")
            continue
        try:
            card = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            err(f"zcode card JSON 解析失败 {p}: {e}")
            continue
        got = (card.get("generated_from") or {}).get("schema_content_hash")
        if got != h:
            err(f"zcode card 陈旧: {p.name} hash={got} ≠ schema {h}")


def check_routing_table(schema: dict) -> None:
    """S2-⑩ 路由表: generated:roster 标记段存在性 + 与 schema 渲染全等（hash 隐含比对）。

    标记段存在性判据单源自 check_projection_guard（守卫脚本与漂移检测共用, 防两处判据漂移）。
    """
    guard_msg = guard_routing_segment(ROUTING_TABLE)
    if guard_msg:
        err(guard_msg)
        return
    text = ROUTING_TABLE.read_text(encoding="utf-8")
    expected = render_roster_markdown(schema)
    mm = re.search(
        r"<!-- BEGIN generated:roster\b.*?<!-- END generated:roster -->\n?",
        text,
        re.S,
    )
    if not mm:
        err(f"路由表 generated:roster 段结构不完整（缺 END 标记）: {ROUTING_TABLE}")
        return
    if mm.group(0) != expected:
        err("路由表 generated:roster 段与 schema 渲染不一致（陈旧或被手改）")


def check_bindings_integrity(members: list[dict], bindings: list[dict]) -> None:
    """S2-⑪ runtime_bindings 完整性: 成员↔binding 一一对应 + as_definition 存在 + 自洽。"""
    ids_m = [m["agent_id"] for m in members]
    ids_b = [b.get("agent_id", "") for b in bindings]
    for x in sorted(set(ids_m) - set(ids_b)):
        err(f"成员 {x} 缺 runtime_bindings 条目")
    for x in sorted(set(ids_b) - set(ids_m)):
        err(f"runtime_bindings 含未知成员: {x}")
    if len(ids_b) != len(set(ids_b)):
        err("runtime_bindings 存在重复 agent_id")
    for b in bindings:
        aid = b.get("agent_id", "?")
        rel = str(b.get("as_definition", ""))
        if not rel.startswith("AgentSwarm/agents/definitions/"):
            err(f"{aid}: as_definition 未指向 AgentSwarm/agents/definitions/: {rel!r}")
        elif not (AS_ROOT / rel.removeprefix("AgentSwarm/")).exists():
            err(f"as_definition 缺失: {rel}（成员 {aid}）")
        if b.get("zcode_subagent") != aid:
            err(f"{aid}: zcode_subagent={b.get('zcode_subagent')!r} ≠ agent_id")
        zt = str(b.get("zs_agent_toml", ""))
        if not zt.endswith(f"/{aid}.toml"):
            err(f"{aid}: zs_agent_toml 与 agent_id 不自洽: {zt!r}")
        zc = str(b.get("zcode_agent_card", ""))
        if not zc.endswith(f"/{aid}.json"):
            err(f"{aid}: zcode_agent_card 与 agent_id 不自洽: {zc!r}")
    agents_dir = ZS_ROOT / ".team" / "agents"
    if agents_dir.is_dir():
        known = {f"{b['agent_id']}.toml" for b in bindings}
        for f in sorted(agents_dir.glob("*.toml")):
            if f.name == "dev.toml":
                continue  # 裁定: ZS 引导 agent dev.toml 永不纳入 schema 席位
            if f.name not in known:
                warn(f"ZS .team/agents 存在 schema 外席位 toml: {f.name}")


def check_feishu_roster(schema: dict) -> None:
    """S2-⑫ feishu roster hook: docs/generated/feishu-roster.json 存在性 + hash 一致。

    告警推送接口 notify_feishu_drift 留待 S4 接线（schema alert_target）。
    """
    if not FEISHU_ROSTER.exists():
        err(f"feishu roster 镜像缺失: {FEISHU_ROSTER}")
        return
    try:
        data = json.loads(FEISHU_ROSTER.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        err(f"feishu roster JSON 解析失败: {e}")
        return
    h = schema_content_hash(schema)
    got = (data.get("generated_from") or {}).get("schema_content_hash")
    if got != h:
        err(f"feishu roster 陈旧: hash={got} ≠ schema {h}")


def check_memory_limits(members: list[dict]) -> None:
    """第 13 类: 席位 MEMORY.md 体量阈值 (ORIGINFORCE/agents/<seat>/MEMORY.md)。

    超 MEMORY_WARN_BYTES (3072B) → warn; 超 MEMORY_ERR_BYTES (5120B) → err;
    文件缺失 → warn (身份包尚未生成, 不算 ERROR)。schema members 集合驱动, 避免误扫非 schema 席位。
    """
    agents_dir = ORIGINFORCE_ROOT / "agents"
    if not agents_dir.is_dir():
        warn(f"agents 目录缺失: {agents_dir} (无法执行 memory_limits 检查)")
        return
    known = {m.get("agent_id", "") for m in members} - {""}
    for aid in sorted(known):
        p = agents_dir / aid / "MEMORY.md"
        if not p.exists():
            warn(f"成员 {aid} MEMORY.md 缺失 (席位未生成身份包, 不计 ERROR)")
            continue
        sz = p.stat().st_size
        if sz >= MEMORY_ERR_BYTES:
            err(f"成员 {aid} MEMORY.md {sz}B 超 ERR 阈值 {MEMORY_ERR_BYTES}B")
        elif sz >= MEMORY_WARN_BYTES:
            warn(f"成员 {aid} MEMORY.md {sz}B 超 WARN 阈值 {MEMORY_WARN_BYTES}B")


def check_hq_registry() -> None:
    """第 14 类: 数字总部 Registry 不变量 (F1-F5)。

    复用 check_hq_registry.py 单源检查逻辑 (truth_source 可解析 / overview 可渲染 /
    id 匹配 / 总部回链块)。ERROR → err；该脚本自身 rc 非零也计 err（防漂移复发）。
    """
    checker = Path(__file__).resolve().parent / "check_hq_registry.py"
    if not checker.exists():
        warn(f"check_hq_registry.py 缺失: {checker} (无法执行第14类检查)")
        return
    try:
        rc = subprocess.run(
            [sys.executable, str(checker)], capture_output=True, text=True, timeout=60
        )
    except Exception as exc:
        err(f"第14类 hq_registry 检查异常: {exc}")
        return
    if rc.returncode != 0:
        for line in (rc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("-"):
                err(f"hq_registry: {line.lstrip('- ')}")


def notify_feishu_drift(errors: list[str]) -> None:
    """留接口 (S4): drift ERROR 推送飞书 wiki 漂移告警中心（schema alert_target）。"""
    return None


def main() -> int:
    schema = load_schema(SCHEMA_PATH)
    if schema is None:
        print(f"[ERROR] schema 不可解析，中止: {SCHEMA_PATH}")
        return 1
    members = check_schema_basic(schema)
    bindings = bindings_of(schema)
    check_zcode_registration(members)
    check_vs_spec(members, parse_spec_defaults())
    check_definitions(members, bindings)
    check_teams_yaml(members)
    check_tools_vs_roster()
    check_residue()
    check_zs_bindings(bindings)
    check_zcode_cards(schema, bindings)
    check_routing_table(schema)
    check_bindings_integrity(members, bindings)
    check_feishu_roster(schema)
    check_memory_limits(members)
    check_hq_registry()
    notify_feishu_drift(ERRORS)

    for w in WARNS:
        print(f"[WARN]  {w}")
    for e in ERRORS:
        print(f"[ERROR] {e}")
    print(
        f"—— 成员 {len(members)} | binding {len(bindings)} "
        f"| ERROR {len(ERRORS)} | WARN {len(WARNS)}"
        f" {'✗ 有漂移' if ERRORS else '✓ 无 ERROR 级漂移'}"
    )
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""sync_team_schema.py — OriginForce schema v2.0 → 四投影生成器 (S2)。

设计裁定 (architect 评审放行, 2026-10-31):
  - 真相源 docs/team-schema.yaml (只读); 写地址权威 = runtime_bindings.as_definition
  - 四投影:
    a. AS  agents/definitions/*.md  frontmatter 字段级外科手术 (SCHEMA_OWNED_FIELDS 白名单;
       metadata.role/schema.role 绝不混写; 正文与 story_fuse_acceptance 永不改); 缺文件→skeleton+WARN
    b. ZS  .team/agents/<id>.toml   新建全量 / 已存在只 merge 身份键 (自定义键保留);
       runtime 键永不动; dev.toml 永不碰; soul 留空
    c. zcode ~/.zcode/agent-cards/<id>.json 全量 (含 runtime_bindings + schema_content_hash)
       + OF 镜像 docs/generated/agent-cards/; 路由表只写 generated:roster 标记段 (手写表不动)
    d. feishu docs/generated/feishu-roster.json 全量 (schema 事实 + tenant 元数据, 无 chat_id)
  - 三级缺字段: P0 (agent_id + 必填 9 字段) 缺→ERROR 跳过该成员全部投影 exit 1;
    P1 (zs_role/capabilities) 缺→内置默认值+WARN; P2 (soul) 缺→静默
  - 幂等: 产物不含时间戳, 以 schema_content_hash 为版本键; 自检 = 连跑两次第二次零 diff
  - 安全: preflight 检查 AS/ZS/OF 目标路径 git dirty (tracked-modified) → 拒绝 (--force 逃生);
    禁写清单按路径前缀校验命中 abort; 最后 subprocess check_team_drift.py 透传退出码

用法:
  python3 scripts/sync_team_schema.py [--dry-run | --check] [--force]
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_common import (  # noqa: E402
    AS_ROOT,
    GENERATED_DIR,
    LEVEL_TOKEN,
    OF_ROOT,
    ORIGINFORCE_ROOT,
    REQUIRED_MEMBER_FIELDS,
    ROUTING_TABLE,
    SCHEMA_PATH,
    ZCODE_CARDS,
    ZCODE_HOME,
    ZS_DEFAULT_CAPABILITIES,
    ZS_DEFAULT_ROLE,
    ZS_REPORTS_TO,
    ZS_ROOT,
    ZS_RUNTIME_KEYS,
    binding_by_id,
    capabilities_for,
    derive_description,
    dump_json,
    load_schema,
    members_of,
    render_agent_card,
    render_feishu_roster,
    render_roster_markdown,
    schema_content_hash,
    upsert_generated_segment,
)

DRIFT_CHECK = OF_ROOT / "scripts" / "check_team_drift.py"

# 与检测器 DEVIATIONS 同源的写入豁免: schema 为权威但 AS 侧承载现实
# (solution-expert 承载 pi 待落地 / devlead l5 为登记例外已对齐, 写入无意义)
SYRINGE_SKIP = {
    ("solution-expert", "runtime"),
    ("devlead", "can_orchestrate"),
}

OWNED_ORDER = ["level", "capability_tier", "autonomy_scope", "runtime",
               "memory", "can_orchestrate"]

# 禁写清单 (写前按路径前缀校验, 命中 abort)
FORBIDDEN: list[tuple[Path, tuple[str, ...]]] = [
    (AS_ROOT, ("specs/", "team/", "proposals/", "memory/", "skills/")),
    (ZS_ROOT, ("src/", ".team/tasks", ".team/bus.jsonl", ".team/knowledge",
               ".team/contracts", ".team/agents/dev.toml")),
    (ZCODE_HOME, ("agents/", "CLAUDE.md", "settings.json")),
    (ORIGINFORCE_ROOT, ("docs/team-schema.yaml", "agents/solution-expert/",
               "docs/team-roster.md")),
]


@dataclass
class Roots:
    as_root: Path = AS_ROOT
    zs_root: Path = ZS_ROOT
    zcode_cards: Path = ZCODE_CARDS
    routing_table: Path = ROUTING_TABLE
    generated_dir: Path = GENERATED_DIR


@dataclass
class WriteOp:
    path: Path
    label: str
    new: str
    old: str | None  # None = 新建


@dataclass
class Plan:
    ops: list[WriteOp] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warns: list[str] = field(default_factory=list)


# ---------- AS definition 外科手术 ----------


def _fmt_co(member: dict) -> str:
    vals = [str(x).lower() for x in (member.get("can_orchestrate") or [])]
    return "[" + ", ".join(vals) + "]" if vals else "[]"


def _owned_value(key: str, member: dict) -> str:
    if key == "level":
        lvl = str(member.get("level", "")).upper()
        return LEVEL_TOKEN.get(lvl, lvl.lower())
    return str(member.get(key, ""))


def patch_definition_text(text: str, member: dict) -> tuple[str, list[str]]:
    """frontmatter 字段级外科手术: 只动白名单键, 其余字节不动; 无需变更返回原文。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text, []
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return text, []
    changes: list[str] = []
    aid = member["agent_id"]

    # 顶层 name (ZCode subagent_type 寻址键, 必须 == agent_id)
    for i in range(1, end):
        if re.match(r"^name:", lines[i]):
            want = f"name: {aid}"
            if lines[i] != want:
                changes.append(f"name: {lines[i].split(':', 1)[1].strip()} → {aid}")
                lines[i] = want
            break

    # metadata 块 (块边界 = 下一个无缩进顶层键; 防止跨块误插/误改)
    mi = next((i for i in range(1, end) if re.match(r"^metadata:\s*$", lines[i])), None)
    if mi is not None:
        seen: dict[str, int] = {}
        last_meta = mi
        i = mi + 1
        while i < end:
            line = lines[i]
            if line.strip() and not line.startswith("  "):
                break  # metadata 块结束
            mm = re.match(r"^  ([A-Za-z_][A-Za-z0-9_]*):(.*)$", line)
            if mm:
                last_meta = i
                key, val = mm.group(1), mm.group(2).strip()
                seen[key] = i
                if key == "can_orchestrate":
                    want = f"  can_orchestrate: {_fmt_co(member)}"
                    if line != want:
                        changes.append(
                            f"metadata.can_orchestrate: {val} → {_fmt_co(member)}")
                        lines[i] = want
                    j = i + 1
                    while j < end and re.match(r"^    - ", lines[j]):
                        del lines[j]
                        end -= 1
                elif key in OWNED_ORDER:
                    if (aid, key) in SYRINGE_SKIP:
                        i += 1
                        continue
                    want = f"  {key}: {_owned_value(key, member)}"
                    if line != want:
                        changes.append(f"metadata.{key}: {val} → {member.get(key)}")
                        lines[i] = want
            i += 1
        # 白名单键缺失 → 插入 metadata 块尾部 (schema 权威字段必须存在)
        insert_at = last_meta + 1
        for key in OWNED_ORDER:
            if key in seen:
                continue
            val = (_fmt_co(member) if key == "can_orchestrate"
                   else _owned_value(key, member))
            lines.insert(insert_at, f"  {key}: {val}")
            changes.append(f"metadata.{key}: (缺失) → {val}")
            insert_at += 1
            end += 1
    return "\n".join(lines), changes


def skeleton_definition(member: dict, schema_hash: str) -> str:
    aid = member["agent_id"]
    return "\n".join([
        "---",
        f"name: {aid}",
        f"description: {derive_description(member)}",
        "metadata:",
        f"  level: {_owned_value('level', member)}",
        "  role: TODO  # schema.role 是描述句非 slug, 待 AS 治理流程补",
        "  type: executor",
        f"  capability_tier: {_owned_value('capability_tier', member)}",
        f"  autonomy_scope: {_owned_value('autonomy_scope', member)}",
        f"  runtime: {_owned_value('runtime', member)}",
        f"  memory: {_owned_value('memory', member)}",
        f"  can_orchestrate: {_fmt_co(member)}",
        "---",
        "",
        f"# {member.get('name', aid)}",
        "",
        f"> skeleton 由 sync_team_schema.py 生成 (schema_content_hash={schema_hash});"
        " 人设正文待 AS 侧补写。",
        "",
    ])


# ---------- ZS toml ----------

_TOML_SAFE = re.compile(r"[A-Za-z0-9_@/.\- ]*")


def _t_val(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_t_val(x) for x in v) + "]"
    s = str(v)
    if not _TOML_SAFE.fullmatch(s):
        raise ValueError(f"toml 不安全字符: {s!r}")
    return '"' + s + '"'


def zs_toml_text(member: dict, existing: dict | None) -> tuple[str, list[str]]:
    """新建全量 / 已存在 merge 身份键 (自定义键保留, runtime 键永不动)。

    返回 (toml 文本, warns)。P2 脏值策略 (devlead 裁定 20261031):
      - soul 含白名单外字符 (如旧简化版遗留的 ~/.zenswarm 路径) → 净化置空 + WARN,
        键本身保留 (检测器 ⑧ 要求身份键齐全);
      - 自定义键值含白名单外字符 → 跳过该键 + WARN (不崩、不写脏值)。
    """
    aid = member["agent_id"]
    warns: list[str] = []
    soul = "" if existing is None else str(existing.get("soul") or "")
    if soul and not _TOML_SAFE.fullmatch(soul):
        warns.append(f"ZS {aid}: soul 含白名单外字符, 已净化置空 (P2): {soul!r}")
        soul = ""
    ident: list[tuple[str, object]] = [
        ("id", aid),
        ("role", ZS_DEFAULT_ROLE),
        ("reports_to", ZS_REPORTS_TO),
        ("soul", soul),
        ("capabilities", capabilities_for(aid)),
    ]
    runtime = {
        "status": "idle",
        "current_session": "",
        "current_task": "",
        "started_at": 0,
    }
    if existing:
        for k in ZS_RUNTIME_KEYS:
            if k in existing:
                runtime[k] = existing[k]
    lines = [f"{k} = {_t_val(v)}" for k, v in ident]
    lines += [f"{k} = {_t_val(runtime[k])}" for k in ZS_RUNTIME_KEYS]
    if existing:
        reserved = {k for k, _ in ident} | set(ZS_RUNTIME_KEYS)
        for k in sorted(existing):
            if k in reserved:
                continue
            try:
                lines.append(f"{k} = {_t_val(existing[k])}")
            except ValueError:
                warns.append(
                    f"ZS {aid}: 自定义键 {k} 值含白名单外字符, 跳过 (P2)"
                )
    return "\n".join(lines) + "\n", warns


# ---------- 禁写 / preflight ----------


def forbidden_reason(path: Path) -> str | None:
    rp = path.resolve()
    for root, prefixes in FORBIDDEN:
        try:
            rel = rp.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        for pre in prefixes:
            if rel == pre.rstrip("/") or rel.startswith(pre):
                return f"{root.name}:{pre}"
    return None


def git_dirty(repo: Path, targets: list[Path]) -> list[str]:
    """tracked-modified 即 dirty; untracked 新文件放行 (merge 保留自定义键, 不覆盖手写)。"""
    if not (repo / ".git").exists():
        return []
    rels = []
    for t in targets:
        try:
            rels.append(str(t.resolve().relative_to(repo.resolve())))
        except ValueError:
            continue
    if not rels:
        return []
    out = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "--", *rels],
        capture_output=True, text=True,
    )
    return [line for line in out.stdout.splitlines()
            if line.strip() and not line.startswith("??")]


# ---------- plan ----------


def build_plan(schema: dict, roots: Roots) -> Plan:
    plan = Plan()
    h = schema_content_hash(schema)
    bmap = binding_by_id(schema)

    # P0 校验
    valid: list[tuple[dict, dict]] = []
    for m in members_of(schema):
        aid = m.get("agent_id")
        missing = [f for f in REQUIRED_MEMBER_FIELDS if f not in m]
        if not aid or missing:
            plan.errors.append(
                f"P0: 成员 {aid or '?'} 缺 "
                f"{(['agent_id'] + missing)} → 全部投影跳过"
            )
            continue
        b = bmap.get(aid)
        if b is None:
            plan.errors.append(f"P0: 成员 {aid} 缺 runtime_binding → 全部投影跳过")
            continue
        valid.append((m, b))

    # P1 汇总 WARN
    from schema_common import ZS_CAPABILITIES

    unmapped = [m["agent_id"] for m, _ in valid if m["agent_id"] not in ZS_CAPABILITIES]
    if valid:
        plan.warns.append(
            f"P1: ZS 身份键按默认/内置表生成 {len(valid)} 席位"
            f" (zs_role={ZS_DEFAULT_ROLE}, reports_to={ZS_REPORTS_TO},"
            " capabilities=内置声明式映射表)"
        )
    for aid in unmapped:
        plan.warns.append(
            f"P1: {aid} 未登记 capabilities 映射, 回落 {ZS_DEFAULT_CAPABILITIES}"
        )

    for m, b in valid:
        aid = m["agent_id"]

        # a. AS definition 外科手术
        as_rel = str(b.get("as_definition", "")).removeprefix("AgentSwarm/")
        if not as_rel:
            plan.errors.append(f"P0: {aid} binding 缺 as_definition")
        else:
            p = roots.as_root / as_rel
            if p.exists():
                old = p.read_text(encoding="utf-8")
                new, changes = patch_definition_text(old, m)
                if changes:
                    plan.ops.append(WriteOp(p, f"AS definition {aid}", new, old))
                    plan.warns.append(f"AS {aid}: {'; '.join(changes)}")
            else:
                plan.ops.append(WriteOp(p, f"AS definition {aid} (skeleton)",
                                        skeleton_definition(m, h), None))
                plan.warns.append(f"AS {aid}: definition 缺失, 生成 skeleton (正文待补)")

        # b. ZS toml
        zs_rel = str(b.get("zs_agent_toml", "")).removeprefix("ZenSwarm/")
        if not zs_rel:
            plan.errors.append(f"P0: {aid} binding 缺 zs_agent_toml")
        else:
            p = roots.zs_root / zs_rel
            existing: dict | None = None
            skip = False
            if p.exists():
                try:
                    existing = tomllib.loads(p.read_text(encoding="utf-8"))
                except Exception as e:  # noqa: BLE001
                    plan.errors.append(f"ZS {aid}: toml 解析失败, 跳过 ({e})")
                    skip = True
            if not skip:
                old = (p.read_text(encoding="utf-8")
                       if existing is not None else None)
                new, zs_warns = zs_toml_text(m, existing)
                plan.warns.extend(zs_warns)
                if old != new:  # 幂等闸: 二次跑内容一致则零 diff
                    plan.ops.append(WriteOp(p, f"ZS toml {aid}", new, old))

        # c. zcode card + OF 镜像
        card = dump_json(render_agent_card(m, b, h))
        for p in (roots.zcode_cards / f"{aid}.json",
                  roots.generated_dir / "agent-cards" / f"{aid}.json"):
            old = p.read_text(encoding="utf-8") if p.exists() else None
            if old != card:
                tag = "OF镜像" if "generated" in str(p) else "部署"
                plan.ops.append(WriteOp(p, f"zcode card {aid} ({tag})", card, old))

    # d. feishu roster (仅含 P0 校验通过的有效成员)
    roster = dump_json(render_feishu_roster(schema, members=[m for m, _ in valid]))
    p = roots.generated_dir / "feishu-roster.json"
    old = p.read_text(encoding="utf-8") if p.exists() else None
    if old != roster:
        plan.ops.append(WriteOp(p, "feishu roster", roster, old))

    # e. 路由表标记段 (仅含 P0 校验通过的有效成员)
    seg = render_roster_markdown(schema, members=[m for m, _ in valid])
    rp = roots.routing_table
    if not rp.exists():
        plan.errors.append(f"路由表缺失, 不凭空创建: {rp}")
    else:
        old = rp.read_text(encoding="utf-8")
        new = upsert_generated_segment(old, seg)
        if new != old:
            plan.ops.append(WriteOp(rp, "路由表 generated:roster 段", new, old))

    return plan


# ---------- main ----------


def _print_diff(op: WriteOp) -> None:
    old = (op.old or "").splitlines(keepends=True)
    new = op.new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old, new,
        fromfile=f"a/{op.path}" if op.old is not None else "/dev/null",
        tofile=f"b/{op.path}",
    )
    sys.stdout.writelines(diff)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="出 diff 不落盘")
    g.add_argument("--check", action="store_true",
                   help="只验证一致性 (幂等自检), 有待变更则 exit 1")
    ap.add_argument("--force", action="store_true", help="豁免 git dirty preflight")
    args = ap.parse_args()

    schema = load_schema(SCHEMA_PATH)
    if schema is None:
        print(f"[ERROR] schema 不可解析，中止: {SCHEMA_PATH}")
        return 2

    roots = Roots()
    plan = build_plan(schema, roots)

    for w in plan.warns:
        print(f"[WARN]  {w}")
    for e in plan.errors:
        print(f"[ERROR] {e}")

    # 禁写清单
    blocked = [op for op in plan.ops if forbidden_reason(op.path)]
    for op in blocked:
        print(f"[ABORT] 禁写清单命中: {op.path} ({op.label})")
    if blocked:
        return 2

    # git dirty preflight (tracked-modified; --force 逃生)
    if not args.force:
        for repo, root_name in ((roots.as_root, "AgentSwarm"),
                                (roots.zs_root, "ZenSwarm"),
                                (OF_ROOT, "OriginForce")):
            targets = [op.path for op in plan.ops
                       if op.path.resolve().is_relative_to(repo.resolve())]
            dirty = git_dirty(repo, targets)
            if dirty:
                print(f"[ABORT] {root_name} 目标路径存在未提交修改 (--force 逃生):")
                for d in dirty:
                    print(f"  {d}")
                return 2

    if args.check:
        if plan.ops or plan.errors:
            print(f"—— check: {len(plan.ops)} 处待变更 / {len(plan.errors)} 个 P0 ERROR"
                  " (与磁盘不一致)")
            return 1
        print("—— check: 产物与 schema 一致 (幂等确认通过)")
        return 0

    if args.dry_run:
        for op in plan.ops:
            _print_diff(op)
        print(f"—— dry-run: {len(plan.ops)} 处将变更 / {len(plan.errors)} 个 P0 ERROR,"
              " 未落盘")
        return 1 if plan.errors else 0

    for op in plan.ops:
        op.path.parent.mkdir(parents=True, exist_ok=True)
        op.path.write_text(op.new, encoding="utf-8")
        print(f"[WRITE] {op.path} ({op.label})")
    print(f"—— 实跑: {len(plan.ops)} 处已写入, {len(plan.errors)} 个 P0 ERROR")

    if plan.errors:
        return 1

    # 生成器验收面: 检测器透传
    drift = subprocess.run([sys.executable, str(DRIFT_CHECK)])
    return drift.returncode


if __name__ == "__main__":
    sys.exit(main())

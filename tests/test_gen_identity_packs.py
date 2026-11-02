"""gen_identity_packs.py MCP 相关真实行为单测 (T-225)。

覆盖 T-223 新代码:
  - load_mcp_matrix() 返回 list
  - mcp_for_seat() 对无声明席位返回 "-"
  - mcp_for_seat() 对有声明席位返回含「MCP 工具」表头

不 mock 被测逻辑: 真读 ~/.claude.json / ~/.qwen/settings.json 与 AS definitions;
无声明席位的用例用真实不存在席位 + 真实无 mcp 声明的席位双验证。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gen_identity_packs as gip

TABLE_HEAD = "| MCP 工具 | 服务器 | 状态 |"


# ── load_mcp_matrix ────────────────────────────────────────────
def test_load_mcp_matrix_returns_sorted_list():
    m = gip.load_mcp_matrix()
    assert isinstance(m, list)
    assert all(isinstance(x, str) and x for x in m)
    assert m == sorted(m), "矩阵必须有序 (去重后 sorted)"
    assert len(m) == len(set(m)), "矩阵不得重复"


def test_load_mcp_matrix_merges_multiple_sources():
    """两个来源文件的 mcpServers 并集: 矩阵 ⊇ 任一源单独读出的键集合。"""
    import json
    from pathlib import Path as P

    matrix = set(gip.load_mcp_matrix())
    per_source = []
    for p in (P.home() / ".claude.json", P.home() / ".qwen" / "settings.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            per_source.append(set((d.get("mcpServers") or {}).keys()))
        except Exception:
            continue
    if not per_source:
        pytest.skip("两个 MCP 来源文件均不可读(环境)")
    for src in per_source:
        assert src <= matrix, f"矩阵遗漏来源键: {src - matrix}"


# ── mcp_for_seat: 无声明 ───────────────────────────────────────
def test_mcp_for_seat_returns_dash_for_unknown_seat():
    assert gip.mcp_for_seat("definitely-not-a-seat-xyz", matrix=["swarm"]) == "-"


def test_mcp_for_seat_returns_dash_for_empty_declaration():
    assert gip.mcp_for_seat("x", mcp_list=[], matrix=["swarm"]) == "-"


def test_mcp_for_seat_returns_dash_for_real_seat_without_mcp():
    """真实席位中挑一个 frontmatter 无 depends_on.mcp 的, 必须返回 '-'。"""
    as_def_dir = gip.AS / "agents" / "definitions"
    if not as_def_dir.is_dir():
        pytest.skip("AS definitions 目录不存在")
    candidates = []
    for p in sorted(as_def_dir.glob("*.md")):
        d = gip.extract_as_definition(p.stem)
        deps = ((d or {}).get("frontmatter") or {}).get("depends_on") or {}
        if not (isinstance(deps, dict) and deps.get("mcp")):
            candidates.append(p.stem)
    if not candidates:
        pytest.skip("所有席位均声明 mcp(环境)")
    for seat in candidates[:3]:
        assert gip.mcp_for_seat(seat, matrix=["swarm"]) == "-", seat


# ── mcp_for_seat: 有声明 ───────────────────────────────────────
def test_mcp_for_seat_table_header_for_declared_seat():
    out = gip.mcp_for_seat("backend-agent", matrix=["swarm"])
    assert out.startswith(TABLE_HEAD), out
    assert "swarm_code_search" in out
    assert "✓ 矩阵内" in out, "声明工具在矩阵内必须标记 ✓"


def test_mcp_for_seat_marks_out_of_matrix_tool():
    """声明了但不在矩阵里的工具 → ⚠ 不在矩阵, 且不得清空表。"""
    out = gip.mcp_for_seat("fake", mcp_list=["not_in_matrix_tool"], matrix=["swarm"])
    assert out.startswith(TABLE_HEAD)
    assert "⚠ 不在矩阵" in out


def test_mcp_for_seat_expands_all_tools_wildcard():
    out = gip.mcp_for_seat("fake", mcp_list=["全部 MCP 工具"], matrix=["swarm", "notion"])
    assert out.startswith(TABLE_HEAD)
    assert "all @ swarm" in out and "all @ notion" in out
    assert out.count("✓ 矩阵内") == 2


def test_mcp_for_seat_real_declared_seats_all_render_table():
    """真实扫描: 凡 frontmatter 声明 mcp 的席位, 都应渲染出表头。"""
    as_def_dir = gip.AS / "agents" / "definitions"
    if not as_def_dir.is_dir():
        pytest.skip("AS definitions 目录不存在")
    declared = []
    for p in sorted(as_def_dir.glob("*.md")):
        d = gip.extract_as_definition(p.stem)
        deps = ((d or {}).get("frontmatter") or {}).get("depends_on") or {}
        if isinstance(deps, dict) and deps.get("mcp"):
            declared.append(p.stem)
    if not declared:
        pytest.skip("无席位声明 mcp(环境)")
    matrix = gip.load_mcp_matrix()
    for seat in declared:
        out = gip.mcp_for_seat(seat, matrix=matrix)
        assert out.startswith(TABLE_HEAD), f"{seat} 未渲染 MCP 表: {out[:80]}"

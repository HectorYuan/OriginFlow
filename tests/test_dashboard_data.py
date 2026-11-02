"""dashboard_data.py 真实行为单测 (T-225)。

覆盖 T-222 采集层:
  - collect_drift() 返回 dict 含 errors 键
  - collect_events(n) 返回 ≤n 条且条目含 source/text/sha
  - collect_schema() 返回含 members 的 dict

不 mock 被测逻辑: 全部真跑采集 (git 只读 / yaml 读 / drift 子进程)。
不写 DB、不依赖网络; 外部源不可用时按函数自身降级契约断言, 不跳过核心断言。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dashboard_data as dd


# ── collect_drift ───────────────────────────────────────────────
def test_collect_drift_returns_errors_key():
    d = dd.collect_drift()
    assert isinstance(d, dict)
    assert "errors" in d
    assert isinstance(d["errors"], int)
    assert "ok" in d
    # ok 与 errors 的语义必须自洽 (errors==0 ⇔ ok)
    assert d["ok"] is (d["errors"] == 0)


def test_collect_drift_parses_error_count_from_real_stdout():
    """真跑 drift 脚本, 输出里的 'ERROR <n>' 必须被解析成同一个 n。"""
    d = dd.collect_drift()
    raw = d.get("raw", "")
    if d["errors"] >= 0 and "ERROR" in raw:
        import re
        m = re.search(r"ERROR (\d+)", raw)
        assert m, f"raw 含 ERROR 但无计数: {raw!r}"
        assert int(m.group(1)) == d["errors"]


# ── collect_events ──────────────────────────────────────────────
@pytest.mark.parametrize("n", [1, 3, 10])
def test_collect_events_respects_limit_and_fields(n):
    ev = dd.collect_events(n)
    assert isinstance(ev, list)
    assert len(ev) <= n
    for e in ev:
        assert {"source", "text", "sha"} <= set(e), f"事件条目缺字段: {e}"
        assert e["source"] in ("AS", "ZS")
        assert e["sha"] and len(e["sha"]) >= 7
        assert len(e["text"]) <= 80


def test_collect_events_sorted_by_sha_desc():
    """实测排序口径: 按 sha 字符串降序 (不是按时间), 故前缀切片随 n 变化。"""
    ev = dd.collect_events(10)
    shas = [e["sha"] for e in ev]
    assert shas == sorted(shas, reverse=True), f"未按 sha 降序: {shas}"
    assert len(dd.collect_events(10)) >= len(dd.collect_events(3))


# ── collect_schema ──────────────────────────────────────────────
def test_collect_schema_returns_members():
    s = dd.collect_schema()
    assert isinstance(s, dict)
    assert "members" in s and isinstance(s["members"], list)
    assert s["total"] == len(s["members"])
    assert "by_level" in s and isinstance(s["by_level"], dict)
    if s["members"]:  # schema 存在时应能读到真实席位
        m = s["members"][0]
        assert "agent_id" in m and m["agent_id"]


def test_collect_schema_by_level_covers_every_member():
    s = dd.collect_schema()
    if "error" in s:
        pytest.skip(f"schema 不可读(环境): {s['error']}")
    flat = [x["agent_id"] for b in s["by_level"].values() for x in b]
    assert sorted(flat) == sorted(m["agent_id"] for m in s["members"])


# ── collect_zs_tasks / collect_as_db 降级契约 ───────────────────
def test_collect_zs_tasks_shape_and_state_count():
    z = dd.collect_zs_tasks()
    assert isinstance(z, dict) and "total" in z and "states" in z
    assert z["total"] == len(z["tasks"])
    assert sum(z["states"].values()) == z["total"]


def test_collect_as_db_degrades_to_error_key_when_unavailable():
    """AS DB 不可读时不得抛异常, 必须降级成 {'error': ...}。"""
    d = dd.collect_as_db()
    assert isinstance(d, dict)
    if "error" in d:
        assert "proposals" not in d
    else:
        assert "proposals" in d and isinstance(d["proposals"], int)

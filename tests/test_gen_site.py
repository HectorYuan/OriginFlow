"""gen_site.py 真实行为单测 (T-225)。

覆盖 T-220 新代码:
  - build_context() 必需键 (members/zs/props/drift/events)
  - render_index() 输出含「席位」「最近事件」
  - --force 未配 --only index 被 argparse 拒绝 (退出码 2)

不 mock 被测逻辑: build_context 真跑采集层, render_index 真渲染,
--force 测试走真 argparse; 仅把输出目录 SITE 重定向到 tmp_path 以免写真实 site/。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gen_site


# ── build_context ────────────────────────────────────────────────
def test_build_context_has_required_keys():
    ctx = gen_site.build_context()
    for k in ("members", "zs", "props", "drift", "events"):
        assert k in ctx, f"build_context 缺键 {k}"
    assert isinstance(ctx["members"], list)
    assert isinstance(ctx["zs"], dict) and "total" in ctx["zs"]
    assert isinstance(ctx["props"], int)
    assert isinstance(ctx["drift"], int)
    assert isinstance(ctx["events"], list)


def test_build_context_by_level_partitions_all_members():
    """by_level 是 members 的完整划分 (每席位恰好落入一个等级桶)。"""
    ctx = gen_site.build_context()
    flat = [m["agent_id"] for bucket in ctx["by_level"].values() for m in bucket]
    assert sorted(flat) == sorted(m["agent_id"] for m in ctx["members"])
    assert len(flat) == len(set(flat)), "席位在多个等级桶重复出现"


# ── render_index ────────────────────────────────────────────────
def test_build_context_events_actually_loaded():
    """events 必须真采集到内容, 不能被静默置空 (空 list 也能过 isinstance 断言)。"""
    ctx = gen_site.build_context()
    assert len(ctx["events"]) > 0, "events 为空: 采集链断裂 (dashboard-data.json 有 15 条, git 回落也有)"
    first = ctx["events"][0]
    for k in ("ts", "subj", "src"):
        assert k in first, f"event 行缺键 {k}"
    assert first["subj"], "event 文本不得为空"


def test_render_index_contains_seats_and_recent_events():
    ctx = gen_site.build_context()
    html = gen_site.render_index(ctx)
    assert "席位" in html
    assert "最近事件" in html
    # 真实渲染出来的统计数字与 ctx 一致
    assert f"<b>{len(ctx['members'])}</b><span>席位</span>" in html


def test_render_index_is_wellformed_document():
    html = gen_site.render_index(gen_site.build_context())
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert "<nav>" in html and "</nav>" in html
    assert html.count("<main") == 1


# ── --force 门禁 (argparse 层) ───────────────────────────────────
def test_force_without_only_index_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["gen_site.py", "--force"])
    with pytest.raises(SystemExit) as ei:
        gen_site.main()
    assert ei.value.code == 2, "--force 未配 --only index 必须退出码 2"
    assert "--force 仅允许配 --only index" in capsys.readouterr().err


def test_force_with_only_pages_is_rejected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gen_site.py", "--force", "--only", "pages"])
    with pytest.raises(SystemExit) as ei:
        gen_site.main()
    assert ei.value.code == 2


def test_force_with_only_index_overwrites(tmp_path, monkeypatch):
    """--force --only index 合法: 真跑生成并把已有 index.html 覆盖 (SITE 重定向到 tmp)。"""
    monkeypatch.setattr(gen_site, "SITE", tmp_path)
    idx = tmp_path / "index.html"
    idx.write_text("STALE", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["gen_site.py", "--force", "--only", "index"])
    gen_site.main()
    assert idx.exists()
    assert idx.read_text(encoding="utf-8").startswith("<!doctype html>")
    # 实测行为: main() 无条件 mkdir 四个子目录, --only index 只影响写文件
    for d in ("team", "intel", "cases"):
        assert (tmp_path / d).is_dir(), f"子目录 {d} 应被创建"
        assert not list((tmp_path / d).glob("*.html")), f"--only index 不应写 {d} 页面"


# ── 渲染辅助 ────────────────────────────────────────────────────
def test_event_row_escapes_and_truncates():
    """实测语义: 先截断原始文本到 100 字符, 再做 HTML 转义 (转义后长度可 >100)。"""
    from html import escape

    raw = "<script>x</script>" + "长" * 120
    row = gen_site._event_row({"sha": "abc1234def", "text": raw, "source": "ZS"})
    assert row["ts"] == "abc1234", "sha 取前 7 位"
    assert "<script>" not in row["subj"], "HTML 必须转义"
    assert row["subj"] == escape(raw[:100]), "截断在转义之前"
    assert row["src"] == "ZS"


def test_page_marks_active_nav():
    html = gen_site.page("标题", "<h1>x</h1>", "team/index.html")
    assert 'href="/team/index.html" class=on' in html
    assert 'href="/dashboard.html" class=on' not in html

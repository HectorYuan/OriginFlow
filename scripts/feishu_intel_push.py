#!/usr/bin/env python3
"""feishu_intel_push.py — 本地情报产物 → 飞书园区「情报站」归档索引 (F1a 出站托管, 园区方案 §5.5)。

读侧: AgentSwarm docs/intel(周报)/analysis/audits 最新条目 (真相源, I5 只登记目录+一行摘要不复制正文)
写侧: 更新情报站 wiki 节点 doc 的「当前归档」段 (str_replace 定位, 幂等)
纪律: best-effort 失败不阻塞; 摘要取文件首行标题 (≤60 字)。
用法: python3 scripts/feishu_intel_push.py [--limit 8]"""
import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

INTEL_ROOT = Path("/home/hector/DevSpace/AgentSwarm/docs")
NODE_DOC = "PzHVwzwmoi6iF8kcucScgh2lnce"  # 园区「情报站」
MARK_BEGIN = "<!--INTEL-ARCHIVE-BEGIN-->"
MARK_END = "<!--INTEL-ARCHIVE-END-->"


def first_line(p: Path) -> str:
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip().lstrip("#>- ")
            if ln:
                return ln[:60]
    except OSError:
        pass
    return p.name


def collect(limit: int) -> list[tuple[str, str, str]]:
    """(日期, 类别+条目, 摘要) 按文件 mtime 倒序。"""
    buckets = [("analysis", INTEL_ROOT / "analysis"), ("audits", INTEL_ROOT / "audits"), ("intel 周报", INTEL_ROOT / "intel")]
    rows = []
    for label, d in buckets:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            rows.append((date.fromtimestamp(p.stat().st_mtime).isoformat(), f"{label}/{p.name}", first_line(p)))
    return sorted(rows, reverse=True)[:limit * 2]


def build_section(rows) -> str:
    trs = "".join(
        f"<tr><td><p>{d}</p></td><td><p>{e}</p></td><td><p>{s}</p></td></tr>"
        for d, e, s in rows)
    return (f"{MARK_BEGIN}<h3>当前归档（真相源 AgentSwarm/docs，本页只登记目录 I5）</h3>"
            f"<p>最近 {len(rows)} 条 · 生成 {date.today()} · feishu_intel_push.py</p>"
            f"<table><colgroup><col width-ratio='0.12'/><col width-ratio='0.34'/><col width-ratio='0.54'/></colgroup>"
            f"<thead><tr><th><p>日期</p></th><th><p>条目</p></th><th><p>摘要</p></th></tr></thead>"
            f"<tbody>{trs}</tbody></table>{MARK_END}")


def lark(args: list[str]) -> dict:
    r = subprocess.run(["lark-cli", *args], capture_output=True, text=True)
    import json
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()
    rows = collect(a.limit)
    if not rows:
        print("no intel artifacts found")
        return
    section = build_section(rows)
    # 定位既有归档段 (幂等替换) 或追加; keyword fetch 的结构是 data.document.content 内嵌 id
    f = lark(["docs", "+fetch", "--as", "user", "--doc", NODE_DOC, "--scope", "keyword",
              "--keyword", "当前归档", "--detail", "with-ids", "--format", "json"])
    content = str(((f.get("data") or {}).get("document") or {}).get("content") or "")
    ids = re.findall(r'id="([A-Za-z0-9]+)"', content)
    if ids:
        # 区间重写: 从首个归档标题块到文末 (-1), 覆盖历史重复段
        u = lark(["docs", "+update", "--as", "user", "--doc", NODE_DOC, "--command", "block_replace",
                  "--start-block-id", ids[0], "--end-block-id", "-1", "--doc-format", "xml",
                  "--content", section, "--format", "json"])
        print("archive section replaced" if u.get("ok") else f"replace fail: {str(u.get('error'))[:80]}")
    else:
        u = lark(["docs", "+update", "--as", "user", "--doc", NODE_DOC, "--command", "append",
                  "--doc-format", "xml", "--content", section, "--format", "json"])
        print("archive section appended" if u.get("ok") else f"append fail: {str(u.get('error'))[:80]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""designcanon_inject.py — DesignCanon 公理按席位注入到 agent 上下文 (S4)。

依据: ZS 链3 定论 "结构化字段才有效"（自然语言遵从率≈0）
协议: docs/intel/designcanon-injection-protocol.md
数据源: ~/Obsidian/DesignCanon/ (347 条公理)

用法:
  python3 scripts/designcanon_inject.py --seat devlead                # 输出 devlead 默认公理集
  python3 scripts/designcanon_inject.py --seat devlead --format json  # JSON 格式（bus payload）
  python3 scripts/designcanon_inject.py --list                        # 列出全部席位默认集
"""
from __future__ import annotations
import argparse, glob, os, re, sys
from pathlib import Path

CANON_ROOT = Path.home() / "Obsidian" / "DesignCanon"

# 按席位默认公理集（OriginForce schema intel_feeds.by_seat 已定义）
SEAT_AXIOM_MAP = {
    "devlead": {"domain": "1-Methods-Martin", "filter": None},
    "product-owner": {"domain": "3-People-Weinschenk", "filter": None},
    "architect-agent": {"domain": "1-Methods-Martin", "filter": "arch|system|design|structure"},
    "backend-agent": {"domain": "2-Principles-Lidwell", "filter": "code|error|feedback|simplicity"},
    "frontend-agent": {"domain": "2-Principles-Lidwell", "filter": "visual|aesthetic|contrast|alignment"},
    "pm-agent": {"domain": "3-People-Weinschenk", "filter": "decision|social|emotion"},
    "sprint-master": {"domain": "1-Methods-Martin", "filter": "agile|sprint|task|prior"},
    "data-analyst": {"domain": "2-Principles-Lidwell", "filter": "data|number|metric"},
    "search-agent": {"domain": "4-Concepts", "filter": None},
    "qa-agent": {"domain": "2-Principles-Lidwell", "filter": "error|feedback|test|quality"},
    "test-agent": {"domain": "2-Principles-Lidwell", "filter": "test|error|feedback"},
    "monitor-agent": {"domain": "2-Principles-Lidwell", "filter": "signal|noise|alert"},
    "system-navigator": {"domain": "4-Concepts", "filter": None},
    "principle-check": {"domain": "5-Meta", "filter": None},
    "solution-expert": {"domain": None, "filter": None},  # 全库
    "ops-agent": {"domain": "2-Principles-Lidwell", "filter": "automation|efficiency|system"},
    "docs-agent": {"domain": "2-Principles-Lidwell", "filter": "clarity|simple|writing"},
}


def scan_canon(domain: str | None = None, filter_pattern: str | None = None) -> list[dict]:
    """扫描 DesignCanon 公理。"""
    results = []
    if not CANON_ROOT.exists():
        return results

    dirs = [CANON_ROOT / d for d in os.listdir(CANON_ROOT)
            if (CANON_ROOT / d).is_dir() and d[0].isdigit()]
    if domain:
        dirs = [d for d in dirs if domain.lower() in d.name.lower()]

    for d in sorted(dirs):
        for f in sorted(d.glob("*.md")):
            rel = f.relative_to(CANON_ROOT)
            text = f.read_text(encoding="utf-8", errors="ignore")
            title_m = re.match(r"^#\s+(.+)", text)
            title = title_m.group(1).strip() if title_m else f.stem
            # 前 200 字作为摘要
            body = re.sub(r"^#.*\n", "", text).strip()[:200]
            entry = {
                "id": f"{d.name}/{f.stem}",
                "title": title,
                "domain": d.name,
                "summary": body,
            }
            if filter_pattern:
                if re.search(filter_pattern, title + " " + body, re.I):
                    results.append(entry)
            else:
                results.append(entry)
    return results


def get_seat_axioms(seat_id: str) -> list[dict]:
    """获取指定席位的默认公理集。"""
    config = SEAT_AXIOM_MAP.get(seat_id)
    if not config:
        return []
    return scan_canon(domain=config.get("domain"), filter_pattern=config.get("filter"))


def format_text(axioms: list[dict]) -> str:
    """格式化为可读文本（注入 agent 上下文）。"""
    if not axioms:
        return "（无匹配公理）"
    lines = [f"DesignCanon 公理集（{len(axioms)} 条）\n"]
    for a in axioms:
        lines.append(f"  [{a['id']}]")
        lines.append(f"  {a['title']}")
        lines.append(f"  {a['summary'][:100]}...")
        lines.append("")
    return "\n".join(lines)


def format_json(axioms: list[dict]) -> str:
    """JSON 格式（bus payload axioms 字段）。"""
    return json.dumps({"axioms": axioms}, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat", help="席位 ID")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--list", action="store_true", help="列出全部席位默认集")
    args = ap.parse_args()

    if args.list:
        for sid, cfg in sorted(SEAT_AXIOM_MAP.items()):
            axioms = get_seat_axioms(sid)
            print(f"  {sid:22s} domain={str(cfg.get('domain')):28s} filter={str(cfg.get('filter')):30s} → {len(axioms)} 条")
        return

    if not args.seat:
        ap.error("--seat required (or --list)")

    axioms = get_seat_axioms(args.seat)
    if args.format == "json":
        print(format_json(axioms))
    else:
        print(format_text(axioms))


if __name__ == "__main__":
    import json  # noqa: E402
    main()

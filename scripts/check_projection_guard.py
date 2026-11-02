#!/usr/bin/env python3
"""generated:roster 生成段防覆盖守卫 — check_team_drift 第 10 类检测的独立可执行入口。

背景: sync_team_schema.py 往 ~/.zcode/ROUTING_TABLE.md 追加/更新 generated:roster 标记段,
但该文件被整份重写时生成段会静默丢失, drift 检测只在被跑时被动报错, 没有独立守卫。

本脚本只做一件事: 检查标记段是否存在。
  缺失 → 打印修复提示并 exit 1;
  在位 → exit 0。
drift 检测 (check_team_drift.check_routing_table) 复用 guard_routing_segment() 单源实现,
守卫与漂移检测不产生两套判据。

归属 ops-agent，接线由 qa-agent 维护（check_team_drift.py 第 10 类检测复用本脚本 guard_routing_segment）。

用法:
  python3 scripts/check_projection_guard.py          # 退出码 0/1, 可挂 cron
  python3 -c "from check_projection_guard import guard_routing_segment; ..."
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_common import ROUTING_TABLE  # noqa: E402

MARKER = "<!-- BEGIN generated:roster"
MISSING_MSG = "生成段丢失, 请跑 sync_team_schema.py --force"


def guard_routing_segment(path: Path | None = None) -> str | None:
    """返回 None = 生成段在位; 否则返回错误信息（含修复指引）。"""
    target = path if path is not None else ROUTING_TABLE
    if not target.exists():
        return f"路由表缺失: {target}"
    if MARKER not in target.read_text(encoding="utf-8"):
        return f"{MISSING_MSG} ({target})"
    return None


def main() -> int:
    msg = guard_routing_segment()
    if msg:
        print(msg)
        return 1
    print(f"OK: generated:roster 段在位 ({ROUTING_TABLE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

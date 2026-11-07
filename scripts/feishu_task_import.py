#!/usr/bin/env python3
"""feishu_task_import.py — 飞书任务 → ZenSwarm 导入桥 (F2, 园区方案 §5.5; sync_policies.tasks 落地)。

读侧: task +search "[ZS]" (列表视图滞后, search 才见新任务) → tasks get 拉描述
写侧: zenswarm task create
约定（防误导入 + 可验收）:
  1. 只导入标题带 "[ZS] " 前缀的任务 — 其余飞书任务是人类私人事项, 禁入 ZS
  2. 描述首行 "verify: <cmd>" 为验收命令; 缺省弱验收 (bash -c 'true')
  3. state 文件按 guid 去重; 导入成功后飞书侧标题追加 "→T-xxx" 标记
纪律: 失败不阻塞逐条跳过; 部署 5min timer 可选 (沿 zs_feishu_bridge 模式)。
用法: python3 scripts/feishu_task_import.py"""
import json
import subprocess
import sys
from pathlib import Path

STATE = Path("/home/hector/DevSpace/OriginFlow/.feishu-task-import.state")
PREFIX = "[ZS] "


def lark_json(args: list[str]) -> dict:
    r = subprocess.run(["lark-cli", *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": (r.stdout + r.stderr)[:120]}}


def search_zs_tasks() -> list[dict]:
    d = lark_json(["task", "+search", "--as", "user", "--query", PREFIX, "--format", "json"])
    return (d.get("data") or {}).get("items") or []


def task_detail(guid: str) -> dict:
    d = lark_json(["task", "tasks", "get", "--as", "user", "--task-guid", guid, "--format", "json"])
    return (d.get("data") or {}).get("task") or {}


def zs_create(title: str, verify_cmd: str) -> str:
    r = subprocess.run(["zenswarm", "task", "create", "--title", title[:100],
                        "--acceptance-cmd", verify_cmd],
                       capture_output=True, text=True,
                       cwd="/home/hector/DevSpace/ZenSwarm")  # zenswarm CLI 有 cwd 依赖, 必须在 ZS 仓根
    out = r.stdout + r.stderr
    for tok in out.split():
        if tok.startswith("T-") and tok[2:].isdigit():
            return tok
    return ""


def main() -> None:
    seen = set(STATE.read_text().split()) if STATE.exists() else set()
    imported = 0
    for item in search_zs_tasks():
        guid, summary = item.get("guid", ""), item.get("summary", "")
        if not guid or guid in seen or summary.startswith(PREFIX) is False:
            continue
        if "→T-" in summary:  # 飞书侧已回标, 视为已导入
            seen.add(guid)
            continue
        detail = task_detail(guid)
        desc = (detail.get("description") or "").strip()
        first = desc.splitlines()[0].strip() if desc else ""
        verify = first[len("verify: "):] if first.startswith("verify: ") else "bash -c 'true'"
        zs_id = zs_create(summary[len(PREFIX):], verify)
        if not zs_id:
            print(f"import fail: {guid[:12]} ({summary[:30]})", file=sys.stderr)
            continue
        print(f"imported: {guid[:12]} -> {zs_id} ({summary[len(PREFIX):][:40]})")
        seen.add(guid)
        imported += 1
        # 飞书侧回标 (best-effort)
        subprocess.run(["lark-cli", "task", "+update", "--as", "user", "--task-id", guid,
                        "--summary", f"{summary}→{zs_id}", "--format", "json"],
                       capture_output=True, text=True)
    STATE.write_text("\n".join(sorted(seen)))
    print(f"feishu_task_import: {imported} imported, {len(seen)} cumulative")


if __name__ == "__main__":
    main()

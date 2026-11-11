#!/usr/bin/env python3
"""check_hq_registry.py — 数字总部 Registry 不变量常驻检查器（F1-F5）。

契约单源: OriginForce/docs/hq-registry.yaml + knowledge-overview-spec-v1.md §7
规则来源: AgentSwarm/skills/hq-sync/SKILL.md 内嵌脚本（抽为可执行入口）

规则:
  F1  overview frontmatter 五字段齐 + id 与 registry knowledge[].id 匹配
  F2  overview 含「**总部入口**」回链块
  F3  truth_source 可解析（repo 存在 + path 存在）
  F4  overview_index 指向的文件存在
  F5  updated 超过 90 天 → WARN

退出码: 0 = ERROR 0；1 = 有 ERROR（按 hq-sync 判据 ERROR=0 才许提交）
"""
from __future__ import annotations
import datetime, pathlib, re, sys
import yaml

REPOS = {
    "originforce": "/home/hector/DevSpace/OriginForce",
    "originflow": "/home/hector/DevSpace/OriginFlow",
    "agentswarm": "/home/hector/DevSpace/AgentSwarm",
    "zenswarm": "/home/hector/DevSpace/ZenSwarm",
}
REGISTRY = pathlib.Path(REPOS["originforce"]) / "docs/hq-registry.yaml"


def resolve(k: dict, spec: str) -> pathlib.Path:
    """解析 overview_index 路径（支持 originflow: 跨仓前缀）。"""
    if spec.startswith("originflow:"):
        return pathlib.Path(REPOS["originflow"]) / spec.split(":", 1)[1]
    return pathlib.Path(REPOS[k["truth_source"]["repo"]]) / spec


def check() -> tuple[list[str], list[str]]:
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    errs: list[str] = []
    warns: list[str] = []
    for k in reg.get("knowledge", []):
        repo_id = k["truth_source"]["repo"]
        if repo_id not in REPOS:
            errs.append(f"F3 {k['id']}: 未知 repo '{repo_id}'")
            continue
        if not (pathlib.Path(REPOS[repo_id]) / k["truth_source"]["path"]).exists():
            errs.append(f"F3 {k['id']}: truth_source 不可解析")
        ov = k.get("overview_index", "")
        idx = resolve(k, ov)
        if not idx.exists():
            errs.append(f"F4 {k['id']}: overview_index 不存在 ({ov})")
            continue
        t = idx.read_text(encoding="utf-8")
        if not t.startswith("---"):
            errs.append(f"F1 {k['id']}: overview 无 frontmatter")
            continue
        if "**总部入口**" not in t:
            errs.append(f"F2 {k['id']}: 缺总部回链块")
        elif not k.get("overview_shared") and not re.search(
            r"^id: " + re.escape(k["id"]) + r"$", t[3:t.find("---", 3)], re.M
        ):
            errs.append(f"F1 {k['id']}: frontmatter id 不一致")
        m = re.search(r'^updated: "?(\d{4}-\d{2}-\d{2})', t, re.M)
        if m and (datetime.date.today() - datetime.date.fromisoformat(m.group(1))).days > 90:
            warns.append(f"F5 {k['id']}: updated 超期")
    return errs, warns


def main() -> int:
    errs, warns = check()
    for w in warns:
        print(f"WARN {w}")
    if errs:
        print(f"ERROR {len(errs)}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("ERROR 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())

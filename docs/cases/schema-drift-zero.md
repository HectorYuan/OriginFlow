# Schema 漂移清零 — 24 ERROR → 0

- 治理实战 · 2026-10-19→2026-11-01 · OriginForce+OriginFlow
- 真相源：OriginForce/docs/neo-machine-digital-company-plan-v1.md

## 起点：检测器自报 24 ERROR

team-schema v2.0（17 席位、L1-L5 双轨）落地后，check_team_drift.py 检测器自报 24 ERROR：三处真相同步约定中 zcode 副本已漂移 —— 投影（AS frontmatter / ZS toml / zcode cards / 飞书 roster）与 schema 契约不一致。

## 判定规则

24 ERROR 逐条对齐，判定规则：schema 为准，definitions 改；schema 错的改 schema。

## 清零路径

改完之后，drift 检测器从报警器变成生成器的验收测试 —— sync_team_schema.py --dry-run 预览 diff → 实跑四投影 → 末尾自动 drift 验收闭环。

## 现状

2026-11-01 实测：成员 17 | binding 17 | ERROR 0 | WARN 0 ✓ 无 ERROR 级漂移。cron 6h 巡检常驻，12 类检测覆盖投影合规验收门。

## 经验固化

- 契约（schema）与投影必须有机器可验的等价检查，否则漂移静默累积
- 「schema 为准」的裁决规则消除了双向修改的死循环
- 检测器复用为生成器的验收测试 —— 同一逻辑源 schema_common.py

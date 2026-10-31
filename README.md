# OriginFlow — NeoMachine 集成与调用载体 (L5)

> 职责：把 OriginForce 契约 (schema) 变成运行中的数字组织——投影生成、合规验证、聚合视图。
> 关联：OriginForce (契约, sibling 仓) · AgentSwarm (治理) · ZenSwarm (执行) · herdr/zcode (呈现)

## 组成

- `scripts/sync_team_schema.py` — 四投影生成器（AS frontmatter / ZS toml / zcode cards / 飞书 roster）
- `scripts/check_team_drift.py` — 漂移检测 12 类（投影合规验收门 + cron 6h 巡检）
- `scripts/schema_common.py` — 检测器与生成器单一逻辑源
- `docs/generated/` — 投影镜像（git 可审）

## 用法

```bash
python3 scripts/sync_team_schema.py --dry-run   # 预览 diff
python3 scripts/sync_team_schema.py             # 实跑（末尾自动 drift 验收）
python3 scripts/check_team_drift.py             # 单独巡检
```

## 边界（2026-10-13 devlead 裁定）

- **OriginForce = 纯治理规则 + 组织配置**（冷启动基准，零代码；仅限环境/集成类脚本）
- **一切业务处理归 OriginFlow**（本仓）：读契约 → 产出四域投影 → 验证合规
- 控制指令走各域原生通道（herdr prompt / zenswarm zen / AS 提案），本仓只读聚合

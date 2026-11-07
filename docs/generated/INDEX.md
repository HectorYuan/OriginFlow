---
id: originflow-generated
layer: L5
truth_source: originflow/docs/generated/
tool_layer: false
updated: "2026-11-03"
---

# 生成投影镜像总览

生成器产出的投影镜像（git 可审计）：本目录全部内容由 `scripts/sync_team_schema.py` 等生成器产出，**禁止手改**——手改会在下次生成时被覆盖并触发漂移告警。

## 目录清单

| 条目 | 生成器 | 说明 |
|---|---|---|
| agent-cards/*.json | sync_team_schema.py | 18 席位卡（四投影之一：zcode cards） |
| feishu-roster.json | sync_team_schema.py | 飞书 roster 镜像 |
| teamwork-snapshot.md | 会话扫描 | 多会话协作状态镜像 |
| distill-s3-final.json | 蒸馏通道 | S3 蒸馏产物 |

## 上下游

- 上游：`OriginForce/docs/team-schema.yaml`（唯一手写真相）· 会话/git 现场数据
- 下游：AS definitions / ZS toml / zcode cards / 飞书（四投影消费方）· dashboard 数据面

> **总部入口** · 本集合已登记数字总部 Registry（id: `originflow-generated`）
> 总览视图: `OriginFlow/site/hq/index.html` · 域模型: `OriginForce/docs/digital-hq-domain-model-v1.md` · 版式: `knowledge-overview-spec v1.0`

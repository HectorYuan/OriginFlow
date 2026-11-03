---
id: originflow-adr
layer: L5
truth_source: originflow/docs/adr/
tool_layer: false
updated: "2026-11-03"
---

# ADR 决策记录总览

OriginFlow（L5 集成层）的架构决策档案：每条 ADR 记录一个不可逆度高的架构决策，含公理引用与备选方案。模板 `0001-template.md`，新增 ADR 按序号递增且 immutable。

## 目录清单

| 条目 | 主题 | 状态 |
|---|---|---|
| 0001-neomachine-six-layer.md | NeoMachine 六层体系（DDD 四层 BC 切分 + OriginForce 契约仓裁定） | accepted |
| 0002-digital-hq-bounded-context.md | 数字总部为 OriginFlow 内 Bounded Context（Registry 聚合 + I1-I4 不变量） | proposed |
| 0001-template.md | ADR 模板（背景/决策/公理/备选/后果） | — |

## 上下游

- 上游：`OriginForce/docs/digital-hq-domain-model-v1.md`（ADR-002 的领域模型权威）· DesignCanon 公理库
- 下游：`../design/site-architecture.md`（site 实现依据 ADR-001 分层）· 数字总部 BC 的全部实现

> **总部入口** · 本集合已登记数字总部 Registry（id: `originflow-adr`）
> 总览视图: `OriginFlow/site/hq/index.html` · 域模型: `OriginForce/docs/digital-hq-domain-model-v1.md` · 版式: `knowledge-overview-spec v1.0`

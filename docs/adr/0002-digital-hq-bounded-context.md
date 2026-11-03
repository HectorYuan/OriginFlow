# ADR-002: 数字总部作为 OriginFlow 内的 Bounded Context

> 日期: 2026-11-03
> 状态: proposed (待 Hector 拍板)
> 决策者: Hector
> 关联: OriginForce/docs/digital-hq-domain-model-v1.md · OriginForce/docs/neo-machine-digital-company-plan-v1.md §2/§4 · ADR-001

## 背景

数字总部雏形已在 OriginFlow/site/（五页 HTML 门户），但组织资产（项目/任务/知识库/技能）无统一登记：知识库无总览页、无共享 HTML 组件、无对外对接技能与机制。需要决定数字总部的架构定位：独立仓库？独立服务层？还是既有体系内的显式边界？

## 决策

数字总部（Digital HQ）为 **OriginFlow 内的显式 Bounded Context**，不是新仓、不是第七层。职责 = 组织资产的注册、路由与呈现（Registry of Record）：

- 聚合根 Registry（`OriginForce/docs/hq-registry.yaml` 契约化），四实体 Project/KnowledgeCollection/SkillRef/TaskPointer
- 四条聚合不变量：I1 唯一真相源、I2 工具层禁复制、I3 任务不落状态、I4 总览可渲染
- 接入面复用 AgentSwarm 既有设施（MCP 工具 + envelope v1），不自建第二套协议

术语、不变量、上下游关系（Context Map 增补）权威文本在 `OriginForce/docs/digital-hq-domain-model-v1.md`。

## 依据的公理

<!-- DesignCanon 公理 ID 列表 (结构化字段, 遵守 ZS 链3 定论) -->
axioms:
- "概念完整性 — Registry 一处定义处处使用 (DesignCanon/Martin)"
- "Open Host Service — 总部以 registry schema + overview spec 为发布语言对外开放 (DDD Evans)"
- "反馈原则 — hq-sync 对聚合不变量闭环校验 (跨学科)"
- "Shared Kernel 反例 — 总部对上游只读、上游不感知总部，避免共享内核腐化 (DDD)"

## 备选方案

| 方案 | 优势 | 劣势 | 否决原因 |
|---|---|---|---|
| 独立 hq 仓库 | 边界物理隔离 | 制造第六个孤岛；与 OriginFlow 聚合职责同构重复 | 违反五域方案"防 OriginFlow 长成第六个孤岛"设计原则 |
| 独立总部服务（FastAPI 常驻） | 实时读写 API | 静态站点够用；常驻服务违背 site v0 静态优先设计；维护成本高 | 过度设计（site-architecture.md §5 已规划 v2 再上服务端） |
| 总部契约并入 team-schema.yaml | 少一个契约文件 | 组织身份（成员/席位）与资产登记（项目/知识库/技能）是两个变化速率不同的聚合，合并会互相绑架 | 契约仓红线要求契约小而可审 |

## 后果

### 正面
- 数字总部获得权威边界：术语/不变量/上下游从此可引用，避免"总部"沦为口头概念
- 零新增运行时：复用 OriginFlow 生成器管线与 AgentSwarm 接入面，静态站点不变
- 真相源不搬家纪律制度化为不变量 I1/I2，同步建设风险被机制性阻断

### 负面
- BC 边界是文档约定而非代码强制，依赖 hq-sync 巡检兜底
- registry.yaml 与 team-schema.yaml 两份契约需保持词汇一致（layer/seat），存在漂移面

### 中性
- 飞书/Obsidian 等外部源以 Feed 形态接入，接入时机（二期）不影响 BC 边界

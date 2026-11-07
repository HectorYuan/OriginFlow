---
id: originflow-intel
layer: L4
truth_source: originflow/docs/intel/
tool_layer: false
updated: "2026-11-03"
---

# NeoMachine 情报参谋部索引

> L4 情报层 · 按席位投喂 · OriginFlow 维护 · 同步至 /intel/ 子路径
> 真相源: 各域仓 docs/ · 本文件是索引与投喂路由

## 情报流（日/周频率）

| 来源 | 频率 | 格式 | 消费席位 |
|---|---|---|---|
| swarm-radar 日报 | 日 | md → /radar/ | 全席位 |
| check3 复核结论 | 按需 | md → docs/audits/ | devlead, product-owner |
| session-analytics 周报 | 周 | analysis.json + HTML | devlead, ceo |
| git log 摘要 | 30min | dashboard_data.py → dashboard.html | 全席位 |

## 知识库（沉淀）

### Research 报告（21 项，AgentSwarm docs/research/）

| 主题 | 文件 | 服务席位 |
|---|---|---|
| A2A 协议 | a2a-level-system, a2a-server-impl, agent-interop-protocols | architect-agent, solution-expert |
| 数据库 | agentswarm-database-selection | backend-agent |
| SDK/CLI | agentswarm-sdk-cli | backend-agent, ops-agent |
| 用例设计 | agentswarm-usecase-design | pm-agent, product-owner |
| 初始化 | agentswarm-data-init, agentswarm-final-init | devlead |
| 诊断 | failed-tasks-diagnosis | qa-agent, devlead |
| Agent 维护 | agent-definitions-maintenance | devlead, product-owner |

### DesignCanon 公理库（347 条，~/Obsidian/DesignCanon/）

| 域 | 条数 | 来源 | 接入方式 |
|---|---|---|---|
| Methods (Martin) | 100 | 1-Methods-Martin/ | design-axioms 技能 → ZENSWARM_AXIOM_ARM |
| Principles (Lidwell) | 125 | 2-Principles-Lidwell/ | 同上 |
| People (Weinschenk) | 100 | 3-People-Weinschenk/ | 同上 |
| Meta | 11 | 5-Meta/ | 同上 |
| Arch-Bridge | 1 | 6-Arch-Bridge/ | 架构决策专用 |

### 情报流落盘位置

| 类型 | 路径 | 归档 |
|---|---|---|
| radar 日报 | AgentSwarm/docs/intel/YYYY-WW/ | weekly-digest-scout 技能产出 |
| 审计/复核 | AgentSwarm/docs/audits/ | check3 产出 |
| 分析报告 | AgentSwarm/docs/analysis/ | 各会话产出 |
| 预测校准 | AgentSwarm/docs/predictions/ | PRED 机制 |

## 投喂协议

```yaml
# schema v2.0 intel_feeds.by_seat 已定义（OriginForce）
# 本文件补充: 情报源 → 席位的映射规则

feed_rules:
  - source: swarm-radar
    format: daily_md
    targets: all_seats
    delivery: dashboard.html 事件流区域

  - source: research_reports
    format: md_index
    targets:
      architect-agent: [a2a, interop, protocol]
      backend-agent: [database, sdk, cli]
      pm-agent: [usecase, product]
      solution-expert: [all]

  - source: design_axioms
    format: skill_injection
    targets: all_seats  # ZENSWARM_AXIOM_ARM 默认注入
    structured_field: axioms  # ZS 链3 定论: 结构化字段才有效

  - source: check3_conclusions
    format: audit_md
    targets: [devlead, product-owner]
```

## 与 site /intel/ 的关系

本 INDEX.md 是真相源（OriginFlow 仓内）。
`gen_site.py` 读取本文件 → 渲染 `/intel/index.html`（展示层）。
新增情报源时：改本文件 + 改 schema intel_feeds → 重跑生成器。

## 扩展编目：AgentSwarm docs 集合（2026-11-03 数字总部接入）

AS 大仓不建 INDEX（不搬家纪律），其知识集合由本节统一编目；逐项清单见 `AgentSwarm/docs/research/` 等目录本体。

| AS 集合 | 内容 | 服务席位 | 接入形态 |
|---|---|---|---|
| docs/research/（21 报告） | A2A/数据库/SDK/用例/初始化/诊断/维护 等主题调研 | architect-agent, backend-agent, solution-expert | 上表 Research 段（已有） |
| docs/roadmap/ | 周级以上路线图 | devlead, product-owner | 目录级链接 |
| docs/audits/ | check3 复核档案 | qa-agent, devlead | 情报流段（已有） |
| docs/design/ | trinity-comm 架构、herdr 集成等设计单源 | architect-agent | 目录级链接 |
| skills/（497 技能） | 技能真相源 + 分发机制 | all_seats | Registry skills 段（指针登记） |

## 上下游

- 上游：AS docs 各集合（真相）· swarm-radar/weekly-digest/check3（情报流生产）
- 下游：`/intel/index.html`（site 展示）· schema intel_feeds 投喂 · 数字总部 Registry

> **总部入口** · 本集合已登记数字总部 Registry（id: `originflow-intel`）
> 总览视图: `OriginFlow/site/hq/index.html` · 域模型: `OriginForce/docs/digital-hq-domain-model-v1.md` · 版式: `knowledge-overview-spec v1.0`

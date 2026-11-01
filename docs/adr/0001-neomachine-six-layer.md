# ADR-001: NeoMachine 六层体系架构决策

> 日期: 2026-10-31
> 状态: accepted (Hector 拍板)
> 决策者: Hector
> 关联: OriginForce/docs/neo-machine-digital-company-plan-v1.md

## 背景

五个各自成熟的协作系统 (AgentSwarm/ZenSwarm/OriginForce/herdr/zcode) 各自发明通用语言，同一概念五套名字，没有一个 Bounded Context 被显式声明为权威。导致身份五套真相、任务三套平行、情报无出口。

## 决策

采用 DDD 战略设计，按四层 Bounded Context 重新切分：

| 层 | 域 | 职责 |
|---|---|---|
| L4 情报 | research/radar/DesignCanon | 决策支持 |
| L3 治理 | AgentSwarm | 提案 FSM · 门禁 · 蒸馏 |
| L2 组织 | OriginForce | 唯一身份真相 · 契约 |
| L1 执行 | ZenSwarm | 任务实体 · git 权威 |
| L0 呈现 | herdr + zcode | 人机界面 |

OriginFlow 作为 L5 集成层（聚合视图 + 生成器 + 漂移检测），OriginForce 为永久契约仓（永不承载业务代码）。

## 依据的公理

axioms:
- "概念完整性 — 一处定义处处使用 (DesignCanon)"
- "反馈原则 — drift 检测器闭环 (跨学科)"
- " requisite variety — 门的状态机补足传感器到控制 (Ashby)"

## 备选方案

| 方案 | 优势 | 劣势 | 否决原因 |
|---|---|---|---|
| 单仓库 monorepo | 事务一致 | 五域技术栈不同，合并冲突大 | 技术栈异构 |
| 微服务独立仓 | 完全自治 | 过度设计，当前规模不需要 | 团队=1人 |
| OriginForce 建契约+代码 | 减少仓数 | 契约仓被业务绑架 | 违反零业务代码红线 |

## 后果

### 正面
- 每域独立发布，互不阻塞
- schema 驱动投影，漂移机制性消失
- 行数宪法/极简哲学/治理体系各自保持

### 负面
- 跨域调用需要桥接层（bus 桥、sync 生成器）
- 初始建设成本高（本方案 + site 实现）

### 中性
- 域名分三套体系（opc/origin/zen），需要 DNS 管理

# DesignCanon 结构化注入协议

> S4 补充 · 总设计师设计 · 2026-11-01
> 依据: ZS 链3 定论 "payload 体例 = 唯一有效传递形态"（自然语言遵从率≈0）
> 数据源: ~/Obsidian/DesignCanon/ 347 条公理（Martin 100 + Lidwell 125 + Weinschenk 100 + Meta 11 + Arch-Bridge 1）

## 注入方式

agent 启动或执行设计类任务时，通过 bus 消息的 `axioms` 结构化字段注入：

```json
{
  "type": "task.assigned",
  "payload": {
    "task": "T-202",
    "assignee": "pi",
    "axioms": ["martin-042", "lidwell-031", "weinschenk-007"]
  }
}
```

**规则**：每个架构/设计决策必须引用 ≥1 条公理 ID。引用走结构化字段（payload.axioms 数组），不走自然语言描述。

## 按席位路由的默认公理集

| 席位 | 默认公理集 | 理由 |
|---|---|---|
| devlead | Martin(管理学) 全量 | 团队协调/决策/流程 |
| product-owner | Weinschenk(心理学) 全量 | 用户需求/行为设计 |
| architect-agent | Martin + Arch-Bridge | 系统架构 |
| backend/frontend | Lidwell(设计原则) 核心子集 | 实现/交互 |
| qa-agent | Lidwell + Meta | 测试/质量 |
| solution-expert | 全库 347 条 | 咨询全覆盖 |

## 查询命令

```bash
# 按 ID 查公理
grep -r "martin-042" ~/Obsidian/DesignCanon/

# 按 domain 查
ls ~/Obsidian/DesignCanon/1-Methods-Martin/
```

## 接入点

| 接入点 | 机制 | 状态 |
|---|---|---|
| ZS 派工 | bus.jsonl payload.axioms | ✅ 机制已有 |
| OriginFlow dashboard | 事件流展示 | ✅ gen_dashboard_cli.py |
| 飞书群 | 事件播报含公理引用 | ⏳ 桥过滤后转发 |
| AS 提案 FSM | proposal.yaml axioms 字段 | ⏳ 待接 |

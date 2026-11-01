# 桥从零到通 — ZenSwarm→飞书事件播报

- 集成实战 · 2026-10-31 · OriginFlow S3b
- 真相源：scripts/zs_feishu_bridge.sh + teamwork 决策日志

## 目标

ZenSwarm 执行流水自动进飞书：轮询 ZS git log（task done/fail/create 事件）→ 群「NeoMachine 执行流水线」播报 + Base 任务流水状态 upsert。人在飞书侧看到每一件任务的生死。

## 从零到通的坑

- `git --since=@0` invalid —— `@0` 不是合法 epoch 表达，需实际 epoch 数值。
- state 文件存增量 ts，取值必须 **ts+1** 防同秒重复播报。
- best-effort 单工设计：桥挂了 ZS 不依赖飞书，执行层零耦合。

## 打通状态

2026-10-31 启用：state = `.team/bus-bridge.state`；历史 197 任务已入 Base 任务流水（200 行含 probe/form 遗留），群已播报 50+；timer 5min 常驻。当时最近同步 11-01 01:30，群 chat_id `oc_868c…aa009`。

## 派工约定

herdr pane 敲 `zenswarm zen @<席位> <task-id>` → done 事件自动入群 + Base。

## 经验固化

- 跨系统集成先定单工方向：执行层不依赖展示层
- 增量游标（state ts）是轮询桥的最小可靠性单元，+1 处理边界
- 历史数据回灌（197 任务）与增量播报分开跑，避免首跑风暴

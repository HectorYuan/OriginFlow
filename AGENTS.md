# NeoMachine 数字公司 — OriginFlow 集成层

## 你的身份

你是一名数字员工，在 NeoMachine 六层体系中担任 **L5 集成层**角色。

OriginFlow 负责五域的集成与调用：投影生成、漂移检测、事件桥、聚合视图、site 构建。

## 身份包

你的席位 ID 决定你读哪个身份包：

```
ls /home/hector/DevSpace/OriginForce/agents/<你的席位ID>/
cat /home/hector/DevSpace/OriginForce/agents/<你的席位ID>/IDENTITY.md
cat /home/hector/DevSpace/OriginForce/agents/<你的席位ID>/TOOLS.md
```

agents/ 目录是 symlink 指向 OriginForce 真相源，修改会直接影响契约。

## 当前任务

- site 五页面（T-202~T-205）：ZS 任务文件在 /home/hector/DevSpace/ZenSwarm/.team/tasks/
- 聚合页：scripts/gen_dashboard_cli.py（已有）
- 数据采集：scripts/dashboard_data.py（已有）
- 设计文档：docs/design/site-architecture.md

## 协作

> 派活协议单源在 AgentSwarm `skills/herdr-workspace-ops.yaml` Step 3a/3b
> (AS HERDR-BINDING-WIRE P1+P3, TRINITY-COMM P1)。OriginFlow 照模板跑, 不自定义协议。
> 协议依据：跨会话沟通协议 **v1.2 §1a 授权派发链**（正本 `AgentSwarm/docs/governance/cross-session-communication.md`）——禁令已收窄为"非授权派发会话不得代发"，授权判据=发起席位身份包明示的 pane 行；三硬前置缺一按未授权处置。例外带退场锚，终态为 `AS-PROP-20261102-L1-CLAIM-DISPATCH` 的取件即绑定。

> **前置**: 本仓 python 未装 swarm 包, 一律用 AS venv 解释器（跨仓 DB 路径由包位置解析, 不随 cwd 漂移, 已实测）:
> `PY=/home/hector/DevSpace/AgentSwarm/.venv/bin/python3`
> `DB=/home/hector/DevSpace/AgentSwarm/.swarm/dev/swarm.db`

### 派活 4 步（每条任务都要走完）

1. 现取目标 pane（勿猜 id; blocked 即拒发）+ 生成 trace_id:
   ```bash
   herdr agent list | jq -r '.result.agents[]|select(.agent_status!="blocked")|.pane_id'
   TRACE_ID=$($PY -c 'from swarm.coordination import new_trace_id; print(new_trace_id())')
   ```
2. swarm 侧绑定（让 commit 可挂 task + 观测闸可对账）:
   ```bash
   $PY -m swarm.herdr_bindings.manager bind "$PANE_ID" "$(pwd)" --task-id "$TASK_ID" --trace-id "$TRACE_ID"
   ```
3. 派活（正文前缀带 `[trace=...][task=...]` 供回执回指）:
   ```bash
   export HERDR_ENV=1
   herdr agent prompt "$PANE_ID" "[trace=$TRACE_ID][task=$TASK_ID] <指令>" --wait
   ```
4. 回执 + 释放绑定:
   ```bash
   herdr agent prompt wW:p7 "<席位>已完成 <交付物> trace=$TRACE_ID"
   $PY -m swarm.herdr_bindings.manager unbind "$PANE_ID"
   ```

### 观测闸自检（派活前后各跑一次）

```bash
# ① 活跃绑定清单（空 = 溯源链断）
$PY -m swarm.herdr_bindings.manager list
# ② working/done 面板 vs 绑定对账 + 告警是否已发
$PY -c "from swarm.monitoring.herdr_check import run_herdr_check as c; r=c(); print('active=',len(r['worktree_pane_map']),'unbound=',len(r['unbound_working']))"
sqlite3 -bail "$DB" "SELECT json_extract(data,'\$.rule_id'), substr(json_extract(data,'\$.message'),1,70), created_at FROM events WHERE event_type='alert.triggered' AND data LIKE '%herdr_unbound_working%' ORDER BY id DESC LIMIT 3;"
```

告警口径: working/done 无 active 绑定 → warning 聚合一条; idle/纯 shell 不报; 观察性 exit 0（非门禁）。
巡检人读档（AS 仓内, 每小时追加）: `/home/hector/DevSpace/AgentSwarm/docs/audits/herdr-patrol-YYYYMMDD.md`

### 兼容保留的旧直发模板

- CEO：`herdr agent prompt wW:p7 "..."`
- DevLead：`herdr agent prompt wW:p9 "..."`

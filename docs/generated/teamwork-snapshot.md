# teamwork.md — AgentSwarm 多会话协作真相源
> 协议: multisessions 技能。唯一协作真相源; 状态改动必须回写此处。
> 本文件管"现在谁在干什么"(天级); 周级以上路线见 docs/roadmap/。

## 会话注册表

### droid-main (本会话)
- 职责: 治理批次实施 (AUTO-20261025-010 全批次已落地) + 观察期分析 + 股道制度化
- 能力边界: 出方案需用户拍板; PR 合并走用户先例授权
- 状态 (2026-10-28 00:55): **310b 回退事故已恢复** — commit 1e6b758565,
  496 文件外科恢复到 fadd 版 (blob 三方比对精确提取), fsm.py PR#605/
  dryrun 守卫/17 测试全部 ✅, 49 测试全过, 已推 origin behind=0。
  事故根因: 无路径参数 commit 吃整个 index, index 是陈旧工作树。
  教训入决策日志。
- 阻塞: 无
- 判定已出 (20261031, docs/analysis/unlanded-b-layer-verdict-20261031.md):
  B 层不启用 (自动推从未获可推窗口, §6 拦截恒对); 值班收口 cron 化 =
  触发自动 (behind>5 持续 2 轮落提醒档) + 执行保持人工。实施随下批。
- **005 锁泄漏根治已完成** (AUTO-20261030-005, FSM completed, 0cfc635856
  + b6b20563f1 上 origin): 看门狗本体 2a3a77c136 (并行会话) + 我补 tick
  心跳留痕 (30min INFO, 静默无法与没跑区分) + fdinfo 取证方法档
  (10-31 复检: WRITE 锁 ~90s 瞬态自释放非泄漏, DDL 探针 0.12s 未阻塞)。
  60s 告警 / 300s 熔断 rollback, 6/6 单测。
- **cron 化触发器已实施** (AUTO-20261030-001, FSM completed, 推 origin
  f74481bcc0): divergence_watch 新增 _check_collapse_reminder — behind
  (rev-list develop..origin/develop) >5 持续 ≥2 轮 → 落提醒档
  docs/audits/diverge-reminder-<ts>.md + EventBus
  divergence.collapse_reminder; 回落 ≤5 重置, 同一持续段只落一档; 首轮
  超阈打 COLLAPSE-WATCH 预告行。观察性零自动执行 (单测静态断言锁死:
  函数体无 push/merge/rebase/update-ref)。10/10 单测+真实冒烟静默 ✅;
  features.yaml divergence_watch 条目已登记触发器 evidence。收口动作
  仍走 diverge-collapse 五步法人工/派单, 触发器不改。
- 前注: 10-29~30 连续
  trip 期 jsonl 无样本属边沿触发设计语义 (SKIP 不采样), 非故障; 已修
  SKIP 行不可见洞 (ed89438310)
- 20261030 诊断留痕: "jsonl 断流"误报根因 = DRYRUN-SKIP 只 append
  无 print/写盘, 三天日志零 SKIP 行致误判; 修复后连续 trip 期日志
  可见 SKIP 行
- 自锁治理双修 (2026-10-28 01:2x, 1f2ba9dbb9): promote-autopilot 档
  自锁正反馈已断根 — ①哨兵档归 exclude 不喂 trip 计数 ②trip 边沿
  触发 (连续 trip 只跑一次 dryrun) ③存量 27 档收编 (e3ffbabb34)。
  auto 堆积 30→3, trip 解除。测试隔离修复: 守卫锁打桩根除与系统
  timer 并发碰撞。38 测试全过已推 origin; 310b 里 118 个纯新增垃圾 (yaml
  重复/.bak) 清理待用户单独授权

### droid-railway-duty (herdr 股道值班, pane 会重启换 id)
- 职责: 股道收口执行 (diverge-collapse 五步法); 不做机制改动
- 能力边界: 纯 plumbing, 不碰工作区 staged/untracked; 冲突>5 文件必须停
- 状态 (2026-10-28 00:10): 原 p1B 已关闭 (pane_not_found); 替补 p1G (体系完善, idle)。
  两单已完 (26→0 落档0839 / 8→0 落档2336+SOP); SOP 已入库可被 cron 引用
- 阻塞: 值班 pane 无常驻保证 — pane 关闭即角色空缺 (已实证一次)
- 下一步: 观察期数据出来后判 cron 化; 值班任务到来时按降级链派单

### 其他并行会话
- wR:p1A (omp DIST): Wave-2A 评分器口径修复 — 勿碰其 staged 内容
- wR:p1F (droid 机制修复): 独立机制工作
- 其余 pane 见 herdr pane list; 各 pane 的 staged/untracked 神圣不可侵

### wR:p1A (omp DIST, 2026-10-30)
- 职责: Wave-2A 评分器口径修复 + 会话蒸馏收尾 + 提案台账闭环; 不做股道收口、不碰他 pane staged
- 能力边界: 可外科恢复自己的历史 commit; 不擅自覆盖他线冲突裁决
- 状态 (2026-10-30 01:05): **阻塞全解除** — PR#624 (退避入口3/4 补 root 实参) 已合 `177ea98c04`;
  PR#622 补账恢复已验 (record_skill_usage=2 / all_frameworks_down=4 / 3 测试);
  我的 4 提案 FSM 全闭环: SCORER-C3-ROUTED / FSM-YAML-SPLIT / RESTORE-310B-OMITTED = completed,
  GEN-BACKOFF-ROOT-ARG = draft (待其 PR 合并)。Git 四件套全清 (worktree/本地分支/远端分支 0)。
- **回执 (跨会话询问, 2026-10-30): 「36 tracked 文件磁盘删除是否你方操作」→ ②非我。**
  依据: ①32 件路径与我操作面**交集 0** (我的面 = `skills/*.yaml`、`docs/proposals/*.yaml`、
  `docs/registry/features.yaml`、`docs/proposals/conflicts/`、我新建 signoff);
  ②我执行过的删除仅三类且均有据可查 — `os.remove()` 21 中文 skills (10-28, 未入 git)、
  `git rm` 9 空壳 + `asset-reverify/SKILL.md` (**已提交** `234839f91a`)、
  `git rm --cached -r docs/proposals/conflicts/` (**盘上 1928 文件全保留**);
  ③我唯一一次 `restore --staged` 作用面 = 43 个 `skills/*.yaml` untracked, **非全仓**;
  ④本会话**未执行** `git checkout .` / `restore .`(无 --staged) / `clean` / `reset --hard`;
  ⑤32 件内容归属全为他线 — `data/operation_declarations/*.json`、`check3-auto-retire-round3*`、
  `CEO-DECISION-AUTO-UNAUTHORIZED-*` (我那份是 RESTORE-310B-OMITTED)、`SAVE-UPDATE-FIX.yaml`、
  `signal_producers.py`、`creation_audit.py`、`favicon.ico`、15+ `tests/unit/test_*.py`。
  → 请按你方方案② `git checkout --` 恢复, 我方不恢复、不 add -A。
- 下一步: ①PR#624 之后的 GEN-BACKOFF-ROOT-ARG FSM 推进 ②`split('---')` 重复段根因立项
  (已单元级复现: 紧邻✓ / 带空行✗ / 星号✗ → 追加新段) ③safe_commit 对 gitignore 路径
  `git add` 退出码 1 致 `set -euo pipefail` 中止 — 无法执行「取消跟踪 gitignore 文件」, 需改工具

## 能力边界与降级链
- 股道收口: 值班会话 diverge-collapse (现行) → 无值班会话时 droid-main 代执行 → 全部不可用落量化档待人
- B 层自动推: 观察期 (现行, 一周零误判判定中) → 批量形态启用 → 不启用保持人工

## 决策日志
- 2026-11-01 **scheduler 重启授权部署生效** (用户拍板"现在重启"):
  生产进程 21:16 启动早于收编提交 c847e8d08e (21:41), 三哨兵代码+
  daemon.env 阈值校准悬空未加载。00:28 重启 (PID 2749721), env 双阈值
  已证实载入, NRestarts=0 无崩溃循环, WAL 10MB 健康线内。教训: 收编
  提交上 origin ≠ 部署源生效, 常驻进程需对照进程启动时刻与提交时刻。
- 2026-10-31 **SCHED-MEM-WATCH 收编语义冲突裁定** (c847e8d08e): worktree
  分支 zcode/sched-memory-watch 与 develop 的 merge-tree 零文本冲突是
  假象 — 分支 (10-30 00:43 建) 不知道后续新增的 lock_watchdog/
  disposal_ack 两 tick, 机械合并会静默丢接线。手工三方逐段归队解决。
  教训: merge-tree 零冲突 ≠ 零语义冲突, 双方都改同一 dict/注册表时
  必须人工核对增量段。哨兵首跑即抓 crit (anon 6.4G>旧阈值2G) → 阈值
  按 cgroup 全局口径校准 warn 8G/crit 12G (daemon.env)
- 2026-10-29 **check3 三轮核对 PR#622 补账恢复** (docs/audits/check3-pr622-backfill-recheck-20261029.md):
  9/10 定谳成立, D10 三轮一致推翻 — 「入口3/4 无 root 变量」不实 (两函数签名首参即 root),
  无参调用语义瑕疵 = 退避取证不跟随调用方 root。修正 PR#633 合入 (4 处统一 root 形态)。
  教训: 提交信息里的"修正理由"也要进核对清单 — 理由句失真会沿袭进审计留痕

- 2026-10-28 **垃圾清理甄别先于删除**: "310b 带入 118 垃圾"逐件核对后
  实际仅 2 件形态垃圾 — 12 个 yaml 是 DB 合法视图、94 个是并行会话
  正常成果首次经坏提交上 origin; 删除前必须逐件对 DB+工作区+并行
  注册表核对, 不按提交来源一刀切
- 2026-10-28 **提交卫生红线**: 多会话共享工作区上禁止无路径参数 commit
  (吃整个 index 会把他人 staged 连带提交, 310b 事故根因, 496 文件回退);
  恢复方法论 = blob 三方比对 (好基线/坏提交/origin 现状) 精确提取受害集
- 2026-10-28 值班 pane 非常驻 (p1B 关闭空缺), 替补按"派单时扫描 idle droid pane"动态选 — pane id 不写死
- 2026-10-27 股道收口派单制确立 (根因: 观测/诊断/能力齐备但无执行者)
- 2026-10-27 dryrun 脚本补单实例 flock (根因: 多会话手动跑绕过哨兵层锁; 守卫防并发, 串行连发低危接受)
- 2026-10-26 B 层自动推必须按批 (根因: 逐文件 land = 提交噪音 60%)

- 2026-10-30 **跨会话询问回执机制启用** (36 tracked 文件磁盘消失归因, 规范全文见
  multisessions 技能「跨会话询问与回执协议」+ herdr-operations §6): herdr agent prompt
  双发 (wR:p1A DIST / wR:p15 PYST) → p1A 五点自证「②非我」入本文件 (commit 6e3a3d567a);
  36 集 01:06:35 全部恢复, origin/HEAD 全程零损; staged 1368→0 (1364=conflicts/ 生成物
  取消跟踪被撤 — p1A 报 safe_commit 对 gitignore 路径 git add 退出码 1 致 pipefail 中止,
  工具缺陷待改已列其待办)。遗留: 「谁删的」无认领者 (32 件全属他线) — 再发同类事件按五点
  自证追责; p1A 措辞(我方不恢复)与行为(同分钟恢复)不一致, 已记档为下轮追问点。

- 2026-10-31 **ZenSwarm→飞书桥启用** (S3b, OriginFlow scripts/zs_feishu_bridge.sh): 轮询 ZS git log
  (task done/fail/create) → 群「NeoMachine 执行流水线」(oc_868c2b79a4bfa24a18695350519aa009)
  播报 + Base 任务流水状态 upsert; best-effort 单工 (ZS 不依赖飞书); state=.team/bus-bridge.state
  (增量 ts; git --since=@0 invalid 需实际 epoch, state=ts+1 防同秒重复); 历史 197 任务已入
  Base 任务流水 (200 行含 probe/form 遗留), 群已播报 50+。部署: timer 5min 待注册。
  派工约定: herdr pane 敲 `zenswarm zen @<席位> <task-id>` → done 事件自动入群+Base。

- 2026-10-31 **site 五页面实现已注册 ZS 任务链** (T-202 基础设施+gen_site.py → T-203 门户主页 →
  T-204 聚合页 → T-205 子页三件; deps 链 T-202→[T-203,T-204,T-205]): 归 ZenSwarm 执行层,
  用 zenswarm task verify/done 流程; 验收判据已写 acceptance.cmd (机验); 设计文档
  OriginFlow docs/design/site-architecture.md; 完成后 site/*.html 为 OriginFlow 仓内
  确定性产物, 发布域名待定。origin 组织侧当前焦点 = site 实现; 桥(timer)已运行。

## 同步规则
- 状态变化回写各自状态块; 阻塞必须升级到这里, 不留对话内存
- handoff/派单任务书视为背景, 执行前先核实现场 (git 数字为准)
- 文件所有权: diverge-collapse-*.md 归值班会话; day*-audit / 提案归 droid-main

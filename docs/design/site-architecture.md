# NeoMachine Site 架构设计

> v1.0（2026-11-01）· 状态：设计稿（本地构建，域名待定后发布）
> 归属：OriginFlow（L5 集成层）— site 构建是其核心职责
> 设计系统：从 site.zenlearning.cn index.html 提取 oklch tokens

## 1. 信息架构

```
/                       门户主页 — 六层体系总览 + 席位梯队 + 最新动态
/dashboard.html         聚合页 — 五域实时状态一屏（gen_dashboard.py 产出）
/team/index.html        数字员工名册 — 17 席位卡片（schema 镜像）
/intel/index.html       情报索引 — research + radar + DesignCanon 导航
/cases/index.html       落地案例 — 恢复/事故/协调/提案实战
```

不纳入的（在 zenlearning-site 域名体系）：
- /arch/ — ZenSwarm 组件图 36 页（zenlearning.cn 域）
- /articles/ — AICS/MemT/EdenLive 研究文章（zenlearning.cn 域）
- /radar/ — 情报雷达（zenlearning.cn 域）

## 2. 页面详细设计

### 2.1 门户主页 `/`

| 区块 | 内容 | 数据源 |
|---|---|---|
| hero | NeoMachine 数字公司 + CTA（总控台/名册/情报） | 静态文案 |
| 六层体系 | 6 张架构卡片 + 状态条 | schema v2.0 |
| 席位梯队 | 17 席位按等级分组 | schema members |
| 最近事件 | git log 摘要（task/提案，最近 10 条） | ZS git log |
| 导航 | 四子页入口 + zenlearning 域链接 | 静态 |

### 2.2 聚合页 `/dashboard.html`

| 区块 | 内容 | 数据源 |
|---|---|---|
| 状态指标卡 | 席位/任务done/wip/fail/漂移/桥 | 全域采集 |
| 席位梯队表 | 17行 × (席位/名称/等级/能力/任务数/项目数/状态) | schema + ZS toml |
| 六层架构卡 | 6 卡片（同主页） | schema |
| 任务状态饼图 | SVG donut（done/wip/fail 比例） | ZS tasks |
| 事件流 | 最近 10 条 task/提案事件 | git log + bus.jsonl |
| 漂移明细 | check_team_drift 结果（0=绿/其他=红） | drift 检测输出 |

### 2.3 名册 `/team/index.html`

| 区块 | 内容 |
|---|---|
| 梯队视图 | L5→L1 分行，每席位一卡片（名称/等级/能力档/职责/runtime） |
| 看板视图 | 按等级分栏（kanban 风格纯 CSS） |
| 关联视图 | 每席位的名下任务/负责项目（link 字段聚合） |

### 2.4 情报索引 `/intel/index.html`

三层分栏：
- 情报流：radar 摘要（→ zenlearning/radar/）
- 知识库：research 21 项按主题编目
- 方法论：DesignCanon 347 条速查（→ zenlearning/misc/designcanon/）

### 2.5 案例 `/cases/index.html`

首批 3 篇（md 真相在 OriginFlow docs/cases/，html 展示）：
1. 36 文件恢复复盘（310b + 桥 + 五点自证）
2. Schema 漂移清零（24→0 全过程）
3. 桥从零到通（bus→飞书群播报）

## 3. 技术设计

### 3.1 生成管线

```
scripts/gen_site.py
  ├─ 读 schema v2.0 (yaml.safe_load)
  ├─ 读 ZS .team/tasks/*.toml (tomllib)
  ├─ 读 git log (subprocess)
  ├─ 读 drift 结果 (check_team_drift.py 输出或函数调用)
  ├─ 渲染模板 (str.format 或 f-string, 不引 Jinja2)
  └─ 写 site/*.html (内联 CSS, 自包含)

scripts/gen_dashboard.py
  ├─ 读同上数据源
  └─ 写 site/dashboard.html (聚合页专用, 信息密度更高)
```

### 3.2 CSS 设计系统

从 site.zenlearning.cn index.html 提取 oklch tokens（版权自己的设计系统，复用合法）：

```css
:root {
  --bg: oklch(0.17 0.012 232);
  --surface: oklch(0.205 0.013 232);
  --fg: oklch(0.93 0.006 200);
  --muted: oklch(0.66 0.014 220);
  --accent: oklch(0.82 0.14 168);
  --border: oklch(0.30 0.015 225);
  --serif: Georgia, "Noto Serif SC", serif;
  --sans: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  --mono: "SF Mono", Menlo, Consolas, monospace;
  --maxw: 1160px;
}
```

### 3.3 数据流转

```
schema v2.0 (OriginForce)     ← 人工维护（唯一手写）
       │
       ▼ sync_team_schema.py
ZS .team/agents/*.toml        ← 生成的投影
       │
       ▼ gen_site.py / gen_dashboard.py
site/*.html                   ← 生成的最终页
       │
       ▼ publish-to-site（域名定后）
site.zenlearning.cn 或 opcos.city
```

### 3.4 行数与依赖约束

- gen_site.py + gen_dashboard.py 合计 ≤300 行 Python（标准库 + pyyaml + tomllib）
- site/*.html 纯 HTML+CSS+内联 SVG，零 JS 框架依赖（可加原生 JS 做简单交互）
- 不引入任何 npm/pip 新包

## 4. 发布

域名待定。发布时：
1. 确定域名 → DNS A 记录指向 VPS
2. VPS nginx server block 配置
3. rsync site/ 到 VPS 或 git clone
4. timer 更新路径

发布前：`python3 scripts/gen_site.py && python3 -m http.server -d site/ 8080` 本地预览。

## 5. 后续演进

v0: 静态 HTML（本方案）→ v1: 加原生 JS 交互（图表排序/筛选）→ v2: OriginFlow FastAPI 服务端（实时数据，非定时刷新）

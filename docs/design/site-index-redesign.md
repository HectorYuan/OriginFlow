# site index.html 主站改造设计

> S5 · 总设计师 · 2026-11-01

## 改动范围（零删除）

index.html 当前 34 行（CEO agents 已生成压缩态）。在现有基础上**追加**：

1. **hero 文案改**：`NeoMachine 数字公司` → 保持（已改）
2. **新增 `#system` 区**：六层架构卡片（3×2 grid）+ 状态条
3. **新增 `#team` 区**：席位梯队（L5→L1 分组，17 席位 pill）
4. **导航补 4 项**：+总控台 +名册 +情报 +案例

## 具体设计

### 状态条（追加在六层卡之后）

```html
<div class="stats">
  <div class="stat"><b>17</b>席位</div>
  <div class="stat"><b>187</b>任务done</div>
  <div class="stat"><b>2477</b>提案</div>
  <div class="stat ok"><b>0</b>漂移ERROR</div>
</div>
```

### 导航（header 内追加）

```html
<nav>
  <a href="/" class="on">门户</a>
  <a href="/dashboard.html">总控台</a>
  <a href="/team/">名册</a>
  <a href="/intel/">情报</a>
  <a href="/cases/">案例</a>
  <a href="/index.html">首页</a>
</nav>
```

## 数据

gen_dashboard.py 产出的 dashboard-data.json 已包含全部数据（52KB），
index.html 构建时从 JSON 嵌入静态值（不使用 JS 动态加载）。

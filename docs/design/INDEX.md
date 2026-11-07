---
id: originflow-design
layer: L5
truth_source: originflow/docs/design/
tool_layer: false
updated: "2026-11-03"
---

# 设计文档总览

OriginFlow 的设计文档集：site 信息架构单源与集成层专项设计。`site-architecture.md` 是 site 全部页面与生成管线的权威设计。

## 目录清单

| 条目 | 主题 | 状态 |
|---|---|---|
| site-architecture.md | site 信息架构单源（五页 + gen_site 管线 + oklch tokens + ≤300 行约束） | 设计稿 |
| site-index-redesign.md | 门户 index 页重设计 | 设计稿 |
| multi-agent-resource-allocation-20261031.md | 多智能体资源分配设计 | 设计稿 |

## 上下游

- 上游：ADR-001（分层依据）· `OriginForce/docs/site-upgrade-plan-v1.md`（md+html 双轨纪律）
- 下游：`scripts/gen_site.py` / `gen_dashboard_cli.py`（实现）· `site/*.html`（产物）

> **总部入口** · 本集合已登记数字总部 Registry（id: `originflow-design`）
> 总览视图: `OriginFlow/site/hq/index.html` · 域模型: `OriginForce/docs/digital-hq-domain-model-v1.md` · 版式: `knowledge-overview-spec v1.0`

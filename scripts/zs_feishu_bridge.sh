#!/usr/bin/env bash
# zs_feishu_bridge.sh — ZenSwarm → 飞书 桥 (S3b, AS-PROP-20261025-DIVERGENCE-UNBLOCK S3)
#
# 单向 best-effort: 轮询 ZS git log (task done/fail/create) → 飞书群播报
# + Base 任务流水 upsert。ZS 无飞书/网络断时不影响 ZS 本体 (不阻塞)。
#
# 状态: .team/bus-bridge.state (last processed commit ts)
# 部署: systemd user timer (5min) 或 cron
set -euo pipefail

ZS_ROOT="${ZS_ROOT:-/home/hector/DevSpace/ZenSwarm}"
BASE_TOKEN="${BASE_TOKEN:-O2zCbIQDaasdHysET8FcH8oCn6f}"
CHAT_ID="${CHAT_ID:-oc_868c2b79a4bfa24a18695350519aa009}"
STATE="${STATE:-$ZS_ROOT/.team/bus-bridge.state}"

cd "$ZS_ROOT"

# ── 读上次处理位点 ──
LAST_TS=$(cat "$STATE" 2>/dev/null || echo 1790000000)  # git @0 是 invalid, 保守 epoch 起点

# ── 拉新 task 事件 (git 权威) ──
NEW=$(git log --format='%h|%s|%ad' --date=format:'%s' --grep="task(T-" \
      --since="@$LAST_TS" 2>/dev/null || true)
[ -z "$NEW" ] && exit 0  # 无新事件

MAX_TS="$LAST_TS"
SENT=0
while IFS='|' read -r sha subj ts; do
    [ -z "$sha" ] && continue
    tid=$(echo "$subj" | grep -oE 'T-[0-9]+' | head -1)
    action=$(echo "$subj" | grep -oE '(done|fail|create|verify)' | head -1)
    [ -z "$tid" ] || [ -z "$action" ] && continue
    ts_date=$(date -d "@$ts" '+%m-%d %H:%M' 2>/dev/null || echo '?')

    # 飞书群播报 (best-effort, 失败不阻塞)
    EMOJI="🟢"; [ "$action" = "fail" ] && EMOJI="🔴"; [ "$action" = "create" ] && EMOJI="🔵"
    lark-cli im +messages-send --as bot --chat-id "$CHAT_ID" \
        --msg-type text \
        --content "{\"text\":\"$EMOJI ZenSwarm $action: $tid ($ts_date)\\n$subj\"}" \
        >/dev/null 2>&1 || true

    # Base 任务流水 upsert (状态同步)
    STATE_MAP="done"; [ "$action" = "fail" ] && STATE_MAP="fail"; [ "$action" = "create" ] && STATE_MAP="draft"
    lark-cli base +record-upsert --as user --base-token "$BASE_TOKEN" \
        --table-id "任务流水" \
        --json "{\"task_id\":\"$tid\",\"状态\":[\"$STATE_MAP\"]}" \
        >/dev/null 2>&1 || true

    SENT=$((SENT+1))
    [ "$ts" -gt "$MAX_TS" ] && MAX_TS="$ts"
done <<< "$NEW"

echo "$MAX_TS" > "$STATE"
echo "[bridge] $SENT events processed, state → $MAX_TS"

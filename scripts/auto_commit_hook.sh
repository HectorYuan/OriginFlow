#!/usr/bin/env bash
# auto_commit_hook.sh — task done 时自动 git commit + push（T-221, S6）
#
# 设计前提：OriginFlow 仓内多会话并行，主树常有他人未提交文件。
#   ⇒ 本钩子**只 add 显式传入的文件**，绝不 git add -A / git add .；
#   ⇒ commit 用 pathspec 形式（git commit -m MSG -- <files>），
#      他人已 staged 的内容不会被卷入本次提交。
#
# 用法:
#   scripts/auto_commit_hook.sh <commit_message> [file1 file2 ...]
#
# 环境变量:
#   DRY_RUN=1   只打印将执行的命令，不真跑（只读检查仍会执行）
#   ORIGIN      remote 名，默认 origin
#   BRANCH      推送目标分支，默认当前分支
#   PUSH=0      只 commit 不 push（默认 1）
#
# 退出码:
#   0  成功 / 无改动 / DRY_RUN 完成
#   2  参数错误（缺 message、缺文件参数、危险参数）
#   3  传入文件既不存在也未被 git 跟踪
#   4  git add / commit 失败
#   5  push（含 rebase 重试）失败
#   6  不在 git 仓库内 / detached HEAD
set -euo pipefail

PROG="$(basename "$0")"
DRY_RUN="${DRY_RUN:-0}"
ORIGIN="${ORIGIN:-origin}"
PUSH="${PUSH:-1}"
MAX_RETRY=3

log()  { printf '[%s] %s\n' "$PROG" "$*"; }
# DRY_RUN 下的"将要发生"陈述，避免把计划误读成既成事实
plan() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '[DRY_RUN] (计划) %s\n' "$*"
    else
        printf '[%s] %s\n' "$PROG" "$*"
    fi
}
warn() { printf '[%s] WARN: %s\n' "$PROG" "$*" >&2; }
err()  { printf '[%s] ERROR: %s\n' "$PROG" "$*" >&2; }

usage() {
    cat >&2 <<'EOF'
用法: auto_commit_hook.sh <commit_message> [file1 file2 ...]

只提交显式列出的文件；不传文件参数会被拒绝（退出码 2），以防误提交
并行会话的未提交内容。

  DRY_RUN=1  只打印命令，不执行
  PUSH=0     只 commit，不 push
EOF
}

# ── 打印/执行 分流 ────────────────────────────────────────────────
run() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '[DRY_RUN] %s\n' "$*"
        return 0
    fi
    "$@"
}

# ── 参数校验 ─────────────────────────────────────────────────────
if [ "$#" -lt 1 ]; then
    err "缺少 commit message"
    usage
    exit 2
fi

MSG="$1"
shift

if [ -z "${MSG// /}" ]; then
    err "commit message 为空"
    usage
    exit 2
fi

if [ "$#" -lt 1 ]; then
    err "拒绝执行：未传入任何文件参数。本钩子不允许 git add -A / git add ."
    usage
    exit 2
fi

FILES=()
for f in "$@"; do
    case "$f" in
        -A|--all|-a|.|..|./|"")
            err "拒绝危险参数 '$f'（疑似全量 add）"
            exit 2
            ;;
    esac
    FILES+=("$f")
done

# ── 仓库状态 ─────────────────────────────────────────────────────
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    err "当前目录不在 git 工作树内"
    exit 6
fi

BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$BRANCH" = "HEAD" ]; then
    err "detached HEAD，拒绝提交（请先切到分支）"
    exit 6
fi

# 提案号占位提示（不静默、但仍提交）
if ! printf '%s' "$MSG" | grep -q '\[AS-PROP-'; then
    warn "commit message 缺少 '[AS-PROP-...]' 提案号标签，仍将提交（建议补标签）"
fi

# ── 文件存在性 / 可跟踪性 ─────────────────────────────────────────
for f in "${FILES[@]}"; do
    if [ ! -e "$f" ] && ! git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
        err "文件既不存在也不在版本控制中: $f"
        exit 3
    fi
done

# ── 改动检测（只读）───────────────────────────────────────────────
if [ "$DRY_RUN" = "1" ]; then
    printf '[DRY_RUN] 跳过改动检测（实跑将执行: git status --porcelain -- %s）\n' "${FILES[*]}"
else
    CHANGES="$(git status --porcelain -- "${FILES[@]}" || true)"
    if [ -z "$CHANGES" ]; then
        log "no changes — ${FILES[*]} 无改动，无需提交"
        exit 0
    fi
    log "检测到改动:"
    printf '%s\n' "$CHANGES" | sed 's/^/    /'
fi

# ── add（仅显式文件）─────────────────────────────────────────────
if ! run git add -- "${FILES[@]}"; then
    err "git add 失败"
    exit 4
fi

# ── commit（pathspec 形式：不卷入他人已 staged 内容）─────────────
if ! run git commit -m "$MSG" -- "${FILES[@]}"; then
    err "git commit 失败（可能无实际改动或 hook 拒绝）"
    exit 4
fi
plan "已提交: ${MSG}"

if [ "$PUSH" != "1" ]; then
    log "PUSH=0，跳过 push"
    exit 0
fi

# ── push：fetch → 必要时 rebase → 重试（2/4/8s 退避）────────────
attempt=1
while [ "$attempt" -le "$MAX_RETRY" ]; do
    plan "push 尝试 $attempt/$MAX_RETRY"

    if ! run git fetch "$ORIGIN"; then
        warn "git fetch $ORIGIN 失败（网络/权限？）——继续尝试 push"
    fi

    # origin/<branch> 已前进 ⇒ 先 rebase（不用 --autostash，避免动他人未提交文件）
    if git rev-parse --verify --quiet "$ORIGIN/$BRANCH" >/dev/null; then
        if ! git merge-base --is-ancestor "$ORIGIN/$BRANCH" HEAD; then
            log "$ORIGIN/$BRANCH 已前进，先 rebase 再推"
            if ! run git pull --rebase "$ORIGIN" "$BRANCH"; then
                err "rebase 失败（常见原因: 工作区有他人未提交文件 / 冲突）。请手工处理后重跑。"
                exit 5
            fi
        fi
    else
        warn "$ORIGIN/$BRANCH 不存在，跳过 rebase 检查"
    fi

    if run git push "$ORIGIN" "$BRANCH"; then
        plan "push 成功（尝试 $attempt/$MAX_RETRY）"
        exit 0
    fi

    plan "push 失败（尝试 $attempt/$MAX_RETRY）"
    if [ "$attempt" -lt "$MAX_RETRY" ]; then
        BACKOFF=$(( 2 ** attempt ))   # 2, 4, 8
        plan "退避 ${BACKOFF}s 后重试"
        if [ "$DRY_RUN" != "1" ]; then
            sleep "$BACKOFF"
        fi
    fi
    attempt=$(( attempt + 1 ))
done

err "push 在 $MAX_RETRY 次尝试后仍失败；本地 commit 已保留，未推送。"
exit 5

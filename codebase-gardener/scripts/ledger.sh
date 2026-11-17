#!/usr/bin/env bash
# 上线账本放在单独的 gardener-ledger 分支，和代码分开，只由流水线追加。
#
#   bash ledger.sh open          把账本分支取到 ./ledger 目录；分支还不存在就新建一个空的
#   bash ledger.sh save "说明"   把 ./ledger 里的改动提交并推回账本分支
#   bash ledger.sh audit         列出账本分支上每个提交的作者。正常情况下只应该有流水线机器人。
#                                出现别的名字，说明有人绕过流水线手改了账本，要查清楚。
set -euo pipefail

BRANCH="${GARDENER_LEDGER_BRANCH:-gardener-ledger}"
DIR="${GARDENER_LEDGER_DIR:-ledger}"
BOT_NAME="gardener-bot"
BOT_EMAIL="41898282+github-actions[bot]@users.noreply.github.com"

case "${1:-}" in
  open)
    git fetch -q origin "$BRANCH:refs/remotes/origin/$BRANCH" 2>/dev/null || true
    if git rev-parse -q --verify "refs/remotes/origin/$BRANCH" >/dev/null; then
      git worktree add -q -B "$BRANCH" "$DIR" "origin/$BRANCH"
    else
      git worktree add -q --detach "$DIR" HEAD
      (cd "$DIR" && git checkout -q --orphan "$BRANCH" && git rm -rfq . && git clean -fdxq)
    fi
    touch "$DIR/deploys.jsonl"
    mkdir -p "$DIR/mine-results"
    echo "账本已取出到 $DIR"
    ;;
  save)
    msg="${2:?需要一句说明}"
    cd "$DIR"
    git add -A
    if git diff --cached --quiet; then
      echo "账本没有变化"
      exit 0
    fi
    git -c user.name="$BOT_NAME" -c user.email="$BOT_EMAIL" commit -qm "$msg"
    # 同一时间只有一个流水线写账本（工作流里用 concurrency 保证），推送失败就直接报错，不强推。
    git push -q origin "HEAD:refs/heads/$BRANCH"
    echo "账本已保存：$msg"
    ;;
  audit)
    git fetch -q origin "$BRANCH:refs/remotes/origin/$BRANCH"
    git log "origin/$BRANCH" --format='%an <%ae>' | sort | uniq -c
    ;;
  *)
    echo "用法：bash ledger.sh open | save \"说明\" | audit" >&2
    exit 2
    ;;
esac

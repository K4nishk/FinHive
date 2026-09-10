#!/usr/bin/env bash
# ops/run_builder.sh — decides whether a build pass is warranted.  [KCH-77]
#
# orchestrator.sh is one-shot: it walks the queue and exits. This wrapper is what
# makes development repeatable — a scheduler (launchd, cron) or the tmux cockpit
# calls it, and it starts a pass only if one is warranted. Guards, in order:
#
#   1. another builder already running   -> exit quietly
#   2. an issue in flight (worktree lock) -> exit quietly
#   3. nothing left in the queue          -> exit quietly
#   4. uncommitted changes in ops/        -> exit quietly
#   5. otherwise, run the orchestrator
#
# --loop keeps running passes until the queue is drained (sleep LOOP_INTERVAL
# seconds between passes). Guards 1-2 (lock/worktree) cause a wait-and-retry;
# guards 3-4 (empty queue, dirty ops/) stop the loop.
#
# Reviews are handled independently. A Claude spend cap stops development but must
# never stop code review.
#
# --status is READ-ONLY: it takes no lock and starts nothing.

set -uo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$OPS_DIR/.." && pwd)"
LOG_DIR="$OPS_DIR/logs"
LOG="$LOG_DIR/builder.log"
LOCK="$OPS_DIR/.builder.lock"
WT_LOCK="$OPS_DIR/.worktree.lock"
QUEUE="$OPS_DIR/queue.tsv"
DONE="$OPS_DIR/.completed_issues"

# A pass can legitimately last hours. Only reclaim a lock old enough that the
# process behind it cannot plausibly still be alive.
STALE_AFTER="${STALE_AFTER:-21600}"   # 6h
LOOP_INTERVAL="${LOOP_INTERVAL:-30}"  # seconds between passes in --loop mode

mkdir -p "$LOG_DIR"
cd "$REPO_DIR" || exit 0

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

lock_age() {
  local d="$1"
  [ -d "$d" ] || { echo 0; return; }
  local m; m="$(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d" 2>/dev/null || echo 0)"
  echo $(( $(date +%s) - m ))
}

remaining_count() {
  [ -f "$QUEUE" ] || { echo 0; return; }
  comm -23 \
    <(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$QUEUE" | cut -f2 | sort) \
    <(sort "$DONE" 2>/dev/null || true) | grep -c . || echo 0
}

# ── --status: read-only, touches nothing ─────────────────────────────────────
if [ "${1:-}" = "--status" ]; then
  echo "remaining issues : $(remaining_count)"
  if [ -d "$LOCK" ]; then
    echo "builder          : RUNNING (lock age $(lock_age "$LOCK")s)"
  else
    echo "builder          : idle"
  fi
  if [ -d "$WT_LOCK" ]; then
    echo "worktree         : HELD ($(lock_age "$WT_LOCK")s) — an issue is in flight"
  else
    echo "worktree         : free"
  fi
  if [ -s "$OPS_DIR/.escalations.tsv" ]; then
    echo "escalations      : $(grep -c . "$OPS_DIR/.escalations.tsv") — needs a human"
  fi
  if [ -s "$OPS_DIR/.review_debt.tsv" ]; then
    echo "review debt      : $(grep -c . "$OPS_DIR/.review_debt.tsv") branch(es) unreviewed"
  fi
  echo "last log lines   :"
  tail -5 "$LOG" 2>/dev/null | sed 's/^/    /' || echo "    (no log yet)"
  exit 0
fi

LOOP=0
case "${1:-}" in
  --loop) LOOP=1 ;;
  "") ;;
  *) echo "usage: $(basename "$0") [--status | --loop]" >&2; exit 2 ;;
esac

# ── run_pass: one complete build pass ────────────────────────────────────────
# Returns:  0 = pass ran (orchestrator invoked, regardless of issue-level outcome)
#           1 = skipped (lock or worktree busy) — safe to retry after a delay
#           2 = cannot run (no queue, dirty ops/) — stop looping
run_pass() {
  # guard 1: one builder at a time — mkdir is the atomic primitive
  if ! mkdir "$LOCK" 2>/dev/null; then
    local age
    age="$(lock_age "$LOCK")"
    if [ "$age" -gt "$STALE_AFTER" ]; then
      say "Reclaiming stale builder lock (${age}s)."
      rm -rf "$LOCK"
      mkdir "$LOCK" 2>/dev/null || { say "Lost the race to reclaim. Skipping."; return 1; }
    else
      say "Builder already running (lock age ${age}s). Skipping."
      return 1
    fi
  fi

  # guard 2: never start while an issue is mid-flight
  # "Held" and "abandoned" look identical from outside, and only guard 1 had a
  # staleness escape. A run killed mid-issue left this lock behind and every later
  # pass skipped forever — 5h of "an issue is in flight" with no owner alive and no
  # hint in the message about how to clear it.
  if [ -d "$WT_LOCK" ]; then
    local wt_age wt_pid
    wt_age="$(lock_age "$WT_LOCK")"
    wt_pid="$(cat "$WT_LOCK/pid" 2>/dev/null || true)"
    if [ -n "$wt_pid" ] && kill -0 "$wt_pid" 2>/dev/null; then
      say "An issue is in flight (pid $wt_pid, ${wt_age}s). Skipping."
      rm -rf "$LOCK" 2>/dev/null
      return 1
    fi
    if [ -n "$wt_pid" ]; then
      say "Worktree lock owner (pid $wt_pid) is gone — reclaiming after ${wt_age}s."
      rm -rf "$WT_LOCK"
    elif [ "$wt_age" -gt "$STALE_AFTER" ]; then
      say "Reclaiming stale worktree lock (${wt_age}s, no owner recorded)."
      rm -rf "$WT_LOCK"
    else
      say "An issue is in flight (worktree lock held ${wt_age}s, no owner recorded). Skipping."
      say "  If nothing is running, clear it: rm -rf $WT_LOCK"
      rm -rf "$LOCK" 2>/dev/null
      return 1
    fi
  fi

  # guard 3: anything left to build?
  if [ ! -f "$QUEUE" ]; then
    say "No queue at $QUEUE — run: python3 ops/seed_linear.py --write-queue"
    rm -rf "$LOCK" 2>/dev/null
    return 2
  fi
  local remaining
  remaining="$(remaining_count)"
  if [ "${remaining:-0}" -eq 0 ]; then
    say "Queue exhausted — nothing to build."
    rm -rf "$LOCK" 2>/dev/null
    return 2
  fi

  # guard 4: refuse to run on a dirty ops/
  if [ -n "$(git -C "$REPO_DIR" status --porcelain -- ops/ 2>/dev/null)" ]; then
    say "Uncommitted changes in ops/ — refusing to start (they would be destroyed)."
    rm -rf "$LOCK" 2>/dev/null
    return 2
  fi

  # shellcheck disable=SC1091
  [ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

  say "Starting orchestrator — $remaining issue(s) remaining."
  "$OPS_DIR/orchestrator.sh" >> "$LOG" 2>&1
  local rc=$?
  say "Orchestrator exited with $rc."

  rm -rf "$LOCK" 2>/dev/null
  return 0
}

# Safety net: ensure lock cleanup on unexpected exit
trap 'rm -rf "$LOCK" 2>/dev/null' EXIT
trap 'rm -rf "$LOCK" 2>/dev/null; exit 130' INT TERM

if [ "$LOOP" -eq 1 ]; then
  say "Loop mode — running passes until queue is drained (interval ${LOOP_INTERVAL}s)."
  while true; do
    run_pass
    rc=$?
    case $rc in
      0) ;;
      1) say "Loop: pass skipped (busy). Retrying in ${LOOP_INTERVAL}s."
         sleep "$LOOP_INTERVAL"
         continue
         ;;
      2) say "Loop: cannot continue. Exiting."
         break
         ;;
    esac
    remaining="$(remaining_count)"
    if [ "${remaining:-0}" -eq 0 ]; then
      say "Queue exhausted — loop complete."
      break
    fi
    say "Loop: $remaining issue(s) remaining. Next pass in ${LOOP_INTERVAL}s."
    sleep "$LOOP_INTERVAL"
  done
else
  run_pass
fi
exit 0

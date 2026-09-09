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
#   4. otherwise, run the orchestrator
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

if [ -n "${1:-}" ]; then
  echo "usage: $(basename "$0") [--status]" >&2
  exit 2
fi

# ── guard 1: one builder at a time ───────────────────────────────────────────
# mkdir is the atomic primitive here — test-then-create would race.
if ! mkdir "$LOCK" 2>/dev/null; then
  age="$(lock_age "$LOCK")"
  if [ "$age" -gt "$STALE_AFTER" ]; then
    say "Reclaiming stale builder lock (${age}s)."
    rm -rf "$LOCK"
    mkdir "$LOCK" 2>/dev/null || { say "Lost the race to reclaim. Skipping."; exit 0; }
  else
    say "Builder already running (lock age ${age}s). Skipping."
    exit 0
  fi
fi
trap 'rm -rf "$LOCK" 2>/dev/null' EXIT INT TERM

# ── guard 2: never start while an issue is mid-flight ────────────────────────
if [ -d "$WT_LOCK" ]; then
  say "An issue is in flight (worktree lock held $(lock_age "$WT_LOCK")s). Skipping."
  exit 0
fi

# ── guard 3: anything left to build? ─────────────────────────────────────────
if [ ! -f "$QUEUE" ]; then
  say "No queue at $QUEUE — run: python3 ops/seed_linear.py --write-queue"
  exit 0
fi
remaining="$(remaining_count)"
if [ "${remaining:-0}" -eq 0 ]; then
  say "Queue exhausted — nothing to build."
  exit 0
fi

# ── guard 4: refuse to run on a dirty ops/ ───────────────────────────────────
# The orchestrator's first `git reset --hard` restores the last COMMITTED toolchain
# and deletes untracked files, so uncommitted work in ops/ vanishes silently.
if [ -n "$(git -C "$REPO_DIR" status --porcelain -- ops/ 2>/dev/null)" ]; then
  say "Uncommitted changes in ops/ — refusing to start (they would be destroyed)."
  exit 0
fi

# shellcheck disable=SC1091
[ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

say "Starting orchestrator — $remaining issue(s) remaining."
"$OPS_DIR/orchestrator.sh" >> "$LOG" 2>&1
rc=$?
say "Orchestrator exited with $rc."
exit 0

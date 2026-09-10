#!/usr/bin/env bash
# ops/tmux_orchestrator.sh — the development cockpit.
#
# Creates (or re-attaches to) a tmux session laid out for supervised autonomous
# development: the build loop, its log, the review surfaces, the queue, and repo
# state, each in a pane you can watch and interrupt.
#
# This is the ATTENDED counterpart to a launchd loop. launchd is for unattended
# overnight runs; tmux is for when you want to see what the agent is doing and
# stop it mid-issue. Both drive the same ops/orchestrator.sh.
#
# Usage:
#   ./ops/tmux_orchestrator.sh              # create + attach
#   ./ops/tmux_orchestrator.sh --status     # read-only summary, no session
#   ./ops/tmux_orchestrator.sh --detached   # create without attaching
#   ./ops/tmux_orchestrator.sh --kill       # kill the session (leaves locks alone)
#   ./ops/tmux_orchestrator.sh --reset      # kill session AND clear stale locks
#
# Rules carried over from AssetAuditor/ops (learned the hard way — do not relax):
#   1. Never launch with uncommitted changes in ops/. The orchestrator's first
#      `git reset --hard` restores the last COMMITTED toolchain and deletes
#      untracked scripts — every safety property added since vanishes silently.
#   2. Lock directories must stay gitignored. `git clean -fd` removes untracked
#      directories; an unignored lock deletes itself and mutual exclusion stops
#      working without a word.
#   3. Every worktree toucher takes ops/.worktree.lock. Panes share one checkout.
#   4. Merging a PR while the build runs deletes the base out from under it.
#      Review the stack bottom-up, and expect the branch under the in-flight
#      issue to move.

set -uo pipefail

SESSION="${FINHIVE_TMUX_SESSION:-finhive}"
OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$OPS_DIR/.." && pwd)"
LOG_DIR="$OPS_DIR/logs"
ENV_LOCAL="$OPS_DIR/.env.local"

mkdir -p "$LOG_DIR"

c_red=$'\033[31m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'
ok()   { printf '%s✓%s %s\n' "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s!%s %s\n' "$c_yel" "$c_rst" "$*"; }
bad()  { printf '%s✗%s %s\n' "$c_red" "$c_rst" "$*"; }
dim()  { printf '%s%s%s\n' "$c_dim" "$*" "$c_rst"; }

# ── helpers ──────────────────────────────────────────────────────────────────

have() { command -v "$1" >/dev/null 2>&1; }

# A pane command that survives a missing script: show why, then drop to a shell
# so the pane stays useful instead of closing on you.
guarded() {
  local script="$1" label="$2" cmd="$3"
  if [ -x "$OPS_DIR/$script" ]; then
    printf '%s' "$cmd"
  else
    printf 'clear; echo "%s"; echo; echo "  ops/%s does not exist yet."; echo "  %s"; echo; exec $SHELL' \
      "$label" "$script" "Ticketed — see linear_import.csv (Build the orchestrator loop)."
  fi
}

remaining_count() {
  [ -f "$OPS_DIR/queue.tsv" ] || { echo 0; return; }
  comm -23 \
    <(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$OPS_DIR/queue.tsv" 2>/dev/null | cut -f2 | sort) \
    <(sort "$OPS_DIR/.completed_issues" 2>/dev/null) | grep -c . || echo 0
}

lock_age() {
  local d="$1"
  [ -d "$d" ] || { echo "-"; return; }
  echo "$(( $(date +%s) - $(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d" 2>/dev/null || echo 0) ))s"
}

print_status() {
  echo
  printf '  FinHive — development status\n'
  printf '  %s\n' "$(printf '─%.0s' {1..58})"
  printf '  repo        : %s\n' "$REPO_DIR"
  printf '  branch      : %s\n' "$(git -C "$REPO_DIR" branch --show-current 2>/dev/null || echo '?')"
  printf '  session     : %s\n' "$(tmux has-session -t "$SESSION" 2>/dev/null && echo "RUNNING ($SESSION)" || echo 'not started')"
  printf '  queue       : %s issue(s) remaining\n' "$(remaining_count)"
  printf '  builder lock: %s\n' "$([ -d "$OPS_DIR/.builder.lock" ] && echo "HELD ($(lock_age "$OPS_DIR/.builder.lock"))" || echo 'free')"
  printf '  worktree    : %s\n' "$([ -d "$OPS_DIR/.worktree.lock" ] && echo "HELD ($(lock_age "$OPS_DIR/.worktree.lock")) — an issue is in flight" || echo 'free')"

  local dirty
  dirty="$(git -C "$REPO_DIR" status --porcelain -- ops/ 2>/dev/null | wc -l | tr -d ' ')"
  printf '  ops/ dirty  : %s\n' "$([ "$dirty" -gt 0 ] && echo "$dirty file(s) — WILL BE DESTROYED on reset" || echo 'clean')"
  echo
  printf '  toolchain\n'
  for t in tmux gh coderabbit claude python3 jq; do
    printf '    %-12s %s\n' "$t" "$(have "$t" && echo 'ok' || echo 'MISSING')"
  done
  echo
  if [ -f "$LOG_DIR/builder.log" ]; then
    printf '  last log lines\n'
    tail -5 "$LOG_DIR/builder.log" | sed 's/^/    /'
  else
    dim "  (no builder.log yet)"
  fi
  echo
}

# ── flags ────────────────────────────────────────────────────────────────────

ATTACH=1
case "${1:-}" in
  --status)   print_status; exit 0 ;;
  --detached) ATTACH=0 ;;
  --kill)
    tmux kill-session -t "$SESSION" 2>/dev/null && ok "Killed session '$SESSION'." || warn "No session '$SESSION'."
    dim "Locks left alone — use --reset to clear them too."
    exit 0 ;;
  --reset)
    tmux kill-session -t "$SESSION" 2>/dev/null && ok "Killed session '$SESSION'."
    rm -rf "$OPS_DIR/.builder.lock" "$OPS_DIR/.worktree.lock" 2>/dev/null
    ok "Cleared builder and worktree locks."
    warn "Only do this when you are certain no agent is running."
    exit 0 ;;
  "") ;;
  *) bad "Unknown flag: $1"; sed -n '10,17p' "$0"; exit 2 ;;
esac

# ── preflight ────────────────────────────────────────────────────────────────

have tmux || { bad "tmux not installed. brew install tmux"; exit 1; }

if tmux has-session -t "$SESSION" 2>/dev/null; then
  ok "Session '$SESSION' already exists — attaching."
  [ "$ATTACH" -eq 1 ] && exec tmux attach -t "$SESSION"
  exit 0
fi

# RULE 1 — this guard is the whole reason a session's work survives a reset.
DIRTY_OPS="$(git -C "$REPO_DIR" status --porcelain -- ops/ 2>/dev/null)"
if [ -n "$DIRTY_OPS" ]; then
  bad "Uncommitted changes in ops/ — refusing to start."
  echo
  echo "$DIRTY_OPS" | sed 's/^/    /'
  echo
  dim "The orchestrator's first 'git reset --hard' restores the last COMMITTED"
  dim "toolchain and deletes untracked files. Everything above would vanish"
  dim "silently. Commit or stash first:"
  echo
  echo "    git -C \"$REPO_DIR\" add ops/ && git -C \"$REPO_DIR\" commit -m 'ops: checkpoint'"
  echo
  exit 1
fi

# RULE 2 — locks must never be tracked or they delete themselves under git clean.
if ! grep -qE '^ops/\.\w+\.lock/?$|^ops/\*\.lock' "$REPO_DIR/.gitignore" 2>/dev/null; then
  warn "ops lock directories are not in .gitignore."
  dim "  'git clean -fd' will remove them mid-run and mutual exclusion stops working."
  dim "  Add to .gitignore:  ops/.builder.lock/  ops/.worktree.lock/  ops/logs/  ops/.env.local"
  echo
fi

[ -f "$ENV_LOCAL" ] || warn "ops/.env.local not found — LINEAR_API_KEY etc. will be unset in panes."

# ── build the session ────────────────────────────────────────────────────────

TM="tmux -f /dev/null"                       # ignore the user's ~/.tmux.conf for layout stability
SRC="[ -f '$ENV_LOCAL' ] && . '$ENV_LOCAL';" # every pane inherits credentials

# Fail loudly if the tmux server is unreachable. Without this the rest of the
# script runs against a server that does not exist and still prints success —
# every set-option and send-keys errors to stderr and the ✓ at the end lies.
if ! $TM new-session -d -s "$SESSION" -n build -c "$REPO_DIR" -x 250 -y 60 2>"$LOG_DIR/.tmux.err"; then
  bad "Could not start the tmux server."
  sed 's/^/    /' "$LOG_DIR/.tmux.err" >&2
  echo
  dim "Common causes:"
  dim "  · running inside a sandbox that cannot reach /tmp/tmux-\$UID"
  dim "  · a stale server socket — try: tmux kill-server"
  dim "Run this from your own terminal, not from an automated session."
  rm -f "$LOG_DIR/.tmux.err"
  exit 1
fi
rm -f "$LOG_DIR/.tmux.err"

$TM set-option   -t "$SESSION" -g mouse on
$TM set-option   -t "$SESSION" -g history-limit 50000
$TM set-option   -t "$SESSION" -g status-interval 5
$TM set-option   -t "$SESSION" -g status-style "bg=colour234,fg=colour250"
$TM set-option   -t "$SESSION" -g status-left  "#[bg=colour136,fg=colour234,bold] FinHive #[default] "
$TM set-option   -t "$SESSION" -g status-right "#[fg=colour136]#(git -C $REPO_DIR branch --show-current)#[default] | %H:%M "
$TM set-option   -t "$SESSION" -g status-left-length 30
$TM set-window-option -t "$SESSION" -g window-status-current-style "fg=colour136,bold"

# ── window 0: build ───────────────────────────────────────────────
# left  = the orchestrator (you start it deliberately; it does not auto-run)
# right = live builder log
$TM send-keys -t "$SESSION:build" \
  "$SRC clear; cat <<'EOF'
  BUILD  —  the orchestrator runs one pass over the queue and exits.

    ./ops/run_builder.sh              start a single pass (guards, then orchestrator)
    ./ops/run_builder.sh --loop       keep running passes until the queue is drained
    ./ops/run_builder.sh --status     read-only: queue, locks, recent log
    caffeinate -ims ./ops/run_builder.sh --loop    drain the backlog, keep Mac awake

  Knobs:  IMPL_MODEL (claude-sonnet-5)  MEDIATOR_MODEL (claude-opus-5)
          CR_MAX_ROUNDS=2   MAX_TURNS   LOOP_INTERVAL=30 (secs between passes)

  Nothing merges without you. Review PRs bottom-up.
EOF" C-m

$TM split-window -h -t "$SESSION:build" -c "$REPO_DIR" -p 45
$TM send-keys -t "$SESSION:build.1" \
  "$SRC clear; touch '$LOG_DIR/builder.log'; tail -f '$LOG_DIR/builder.log'" C-m

# ── window 1: review ──────────────────────────────────────────────
# The three review surfaces are independent; passing one does not answer the others.
$TM new-window -t "$SESSION" -n review -c "$REPO_DIR"
$TM send-keys -t "$SESSION:review" \
  "$SRC clear; cat <<'EOF'
  REVIEW  —  three independent surfaces. Passing one does not answer the others.

    1. CLI gate        pre-push, inside orchestrator.sh; blocking findings
                       return to the agent up to CR_MAX_ROUNDS (2), then
                       immediately escalate to a new Linear issue. No third
                       cycle, mediator fix, or dismissal.
    2. SaaS PR review  ./ops/remediate_prs.sh   answers comments on open PRs,
                       pushing to the SAME branch so the stack never deepens.
    3. Deferred        ./ops/review_sweeper.sh  settles debt when CodeRabbit
                       quota ran dry mid-build.  --status prints the ledger.

  A green coderabbit/cli-gate means "no BLOCKING findings" — not "no findings".
  Read the round detail in the PR comment for the rest.
EOF" C-m

$TM split-window -h -t "$SESSION:review" -c "$REPO_DIR" -p 50
$TM send-keys -t "$SESSION:review.1" \
  "$SRC clear; watch -n 30 'gh pr list --state open --limit 20 --json number,title,headRefName,statusCheckRollup --template \"{{range .}}#{{.number}}  {{.headRefName}}  {{.title}}{{\\\"\\n\\\"}}{{end}}\" 2>/dev/null || echo \"gh not authenticated — run: gh auth login\"'" C-m

# ── window 2: queue ───────────────────────────────────────────────
$TM new-window -t "$SESSION" -n queue -c "$REPO_DIR"
$TM send-keys -t "$SESSION:queue" \
  "$SRC clear; '$OPS_DIR/tmux_orchestrator.sh' --status" C-m

$TM split-window -v -t "$SESSION:queue" -c "$REPO_DIR" -p 60
$TM send-keys -t "$SESSION:queue.1" \
  "$SRC clear; cat <<'EOF'
  QUEUE  —  Linear is the source of truth; queue.tsv is the build order.

    python3 ops/seed_linear.py                    dry run (default, safe)
    python3 ops/seed_linear.py --apply            create issues + queue.tsv
    python3 ops/seed_linear.py --apply --project \"P1 Foundation\"

  Requires:  LINEAR_API_KEY   LINEAR_TEAM_KEY   (put them in ops/.env.local)
EOF" C-m

# ── window 3: repo ────────────────────────────────────────────────
$TM new-window -t "$SESSION" -n repo -c "$REPO_DIR"
$TM send-keys -t "$SESSION:repo" \
  "$SRC clear; watch -n 15 'git -C \"$REPO_DIR\" status -sb | head -30; echo; echo \"--- stack (depth ahead of development) ---\"; for b in \$(git -C \"$REPO_DIR\" for-each-ref --format=\"%(refname:short)\" refs/remotes/origin/feature/ 2>/dev/null); do git -C \"$REPO_DIR\" merge-base --is-ancestor \"\$b\" origin/development 2>/dev/null && continue; printf \"%s\\t%s\\n\" \"\$(git -C \"$REPO_DIR\" rev-list --count origin/development..\$b 2>/dev/null)\" \"\$b\"; done | sort -rn | head -10'" C-m

# ── window 4: test ────────────────────────────────────────────────
$TM new-window -t "$SESSION" -n test -c "$REPO_DIR"
$TM send-keys -t "$SESSION:test" \
  "$SRC clear; cat <<'EOF'
  TEST

    cd \"src/Loan Manager\" && python3 -m pytest tests/ -v --cov=loan_manager
    BASE_URL=https://pr-N.vercel.app npx playwright test
    npx playwright test tests/e2e/bot-readiness.spec.ts

  E2E personas (see .claude/skills/e2e-testing):
    /e2e mvp1     MVP1 parity sweep — infrastructure + UI/UX, not just features
    /e2e newuser  signup, session, empty state, time-to-first-value
    /e2e bot      secrets, PII, a11y, hostile input, cost abuse
EOF" C-m

# ── window 5: shell ───────────────────────────────────────────────
$TM new-window -t "$SESSION" -n shell -c "$REPO_DIR"
$TM send-keys -t "$SESSION:shell" "$SRC clear" C-m

$TM select-window -t "$SESSION:build"
$TM select-pane   -t "$SESSION:build.0"

ok "Session '$SESSION' created — windows: build · review · queue · repo · test · shell"
dim "  detach: Ctrl-b d      switch: Ctrl-b <n>      kill: ./ops/tmux_orchestrator.sh --kill"

[ "$ATTACH" -eq 1 ] && exec tmux attach -t "$SESSION"
exit 0

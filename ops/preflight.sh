#!/usr/bin/env bash
# Preflight: prove the toolchain works before spending anything on the queue.
#
# Exists because on 2026-09-13 the builder ran 62 issues over 3 hours, every one
# failing 401, and reported each as a routine per-issue ERROR line. Nothing
# checked auth once up front; nothing counted consecutive failures. One cheap
# call here would have stopped it at the first issue.
#
# Exit 0 = safe to run the builder. Non-zero = do not spend.
# Read-only: takes no lock, creates no branch, writes nothing but its own output.

set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1
OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

FAIL=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=1; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }

echo "preflight — $(date '+%F %T')"
echo

# 1. Auth. The check that would have saved the 3 hours.
#    ANTHROPIC_API_KEY silently overrides the claude.ai subscription login, so a
#    bad value here disables working auth rather than supplementing it.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  case "$ANTHROPIC_API_KEY" in
    sk-ant-api03-*) warn "ANTHROPIC_API_KEY set (api03) — overrides subscription login" ;;
    sk-ant-oat01-*) bad  "ANTHROPIC_API_KEY is an oat01 OAuth token, not an API key — the API returns 401. Unset it." ;;
    *)              bad  "ANTHROPIC_API_KEY is set but is not an sk-ant-api03- key. Unset it." ;;
  esac
else
  ok "ANTHROPIC_API_KEY unset — using claude.ai subscription login"
fi

# One real round trip. Cheapest possible: no tools, one turn, three tokens out.
probe="${TMPDIR:-/tmp}/fh-preflight.$$"
trap 'rm -f "$probe" "$probe.err"' EXIT
if claude -p --output-format json --max-turns 1 \
     'Reply with exactly: PREFLIGHT_OK' </dev/null >"$probe" 2>"$probe.err"; then
  if grep -q PREFLIGHT_OK "$probe" 2>/dev/null; then
    ok "claude -p round trip"
  else
    bad "claude -p returned no usable result — see $probe"
    head -3 "$probe.err" 2>/dev/null | sed 's/^/        /'
  fi
else
  bad "claude -p failed (rc=$?)"
  head -5 "$probe.err" 2>/dev/null | sed 's/^/        /'
fi

# 2. Counting bug. `grep -c . f || echo 0` on an EMPTY file prints "0" AND exits
#    1, so the fallback fires too and the variable becomes "0\n0". Every numeric
#    test on it then errors out and is treated as false — which silently skipped
#    the debt guard and debt phase on every clean run.
#    Only assignments matter: `X="$(grep -c . f || echo 0)"` feeds a numeric test.
#    The same construct inside a message string only misprints.
if grep -RnE '^[^#]*[A-Z_]+="\$\(.*grep -c \..*\|\| *echo 0' "$OPS_DIR"/*.sh >/dev/null 2>&1; then
  bad "grep -c fallback bug still present in a counted assignment:"
  grep -RnE '^[^#]*[A-Z_]+="\$\(.*grep -c \..*\|\| *echo 0' "$OPS_DIR"/*.sh | sed 's/^/        /'
else
  ok "no 'grep -c . || echo 0' counting bugs"
fi

# 3. Agent calls must be bounded. MAX_TURNS bounds turns, not wall clock; an
#    unbounded call held the worktree lock for 3h+ on 2026-09-13.
#    The wrapper sits on the line above the call, so look at both.
if grep -B3 'claude -p ' "$OPS_DIR/orchestrator.sh" 2>/dev/null | grep -qE 'alarm shift|timeout '; then
  ok "claude -p is wall-clock bounded"
else
  bad "claude -p has no timeout — a hung call blocks the pass indefinitely"
fi

# 4. Consecutive-failure circuit breaker.
if grep -q 'CONSEC_ERRS' "$OPS_DIR/orchestrator.sh" 2>/dev/null; then
  ok "consecutive-failure circuit breaker present"
else
  bad "no circuit breaker — errors repeat until the queue is exhausted"
fi

# 5. Stale locks. A lock directory's existence is not liveness; read the pid.
for lk in .builder.lock .worktree.lock; do
  d="$OPS_DIR/$lk"
  [ -d "$d" ] || continue
  pid="$(cat "$d/pid" 2>/dev/null)"
  if [ -n "${FH_LOCK_HOLDER:-}" ] && [ "$pid" = "${FH_LOCK_HOLDER}" ]; then
    # Our own caller holds it: run_builder takes the lock, then runs us.
    ok "$lk held by the calling builder (pid $pid)"
  elif [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    bad "$lk held by LIVE pid $pid — a builder is already running"
  else
    bad "$lk is STALE (pid '${pid:-none}' not running) — rm -rf $d"
  fi
done
[ -d "$OPS_DIR/.builder.lock" ] || [ -d "$OPS_DIR/.worktree.lock" ] || ok "no locks held"

# 6. Queue sanity. wc -l, not grep -c, for the reason in check 2.
if [ -f "$OPS_DIR/queue.tsv" ]; then
  q=$(grep -vcE '^[[:space:]]*#|^[[:space:]]*$' "$OPS_DIR/queue.tsv" 2>/dev/null || true)
  ok "queue.tsv readable — ${q:-0} issue(s)"
else
  bad "no ops/queue.tsv"
fi

# 7. Cumulative spend. The in-loop budget is per-pass and resets on restart, so
#    it has never once fired. This is the real number.
if [ -f "$OPS_DIR/usage.py" ]; then
  tot="$(python3 "$OPS_DIR/usage.py" report --all 2>/dev/null | grep -iE 'TOTAL' | head -1)"
  [ -n "$tot" ] && warn "cumulative spend: $tot"
fi

echo
if [ "$FAIL" -ne 0 ]; then
  printf '\033[31mPREFLIGHT FAILED — do not start the builder.\033[0m\n'
  exit 1
fi
printf '\033[32mPREFLIGHT PASSED.\033[0m\n'

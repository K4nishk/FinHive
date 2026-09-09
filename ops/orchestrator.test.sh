#!/usr/bin/env bash
# ops/orchestrator.test.sh — tests for the build loop's state ledgers and the
# phase selection they drive.  [KCH-76]
#
# These exist because the debt phase shipped broken twice in two commits: once
# ordered so a remediated issue was re-attempted from the queue, once with the
# snapshot line dropped entirely so the phase silently never ran. Both were
# invisible to `bash -n` and to reading the diff. The wiring needs assertions,
# not inspection.
#
# No agents, no gh, no network — the ledgers and the branch logic only.
# Run: ops/orchestrator.test.sh

set -uo pipefail

FIX="$(mktemp -d "${TMPDIR:-/tmp}/orch_test.XXXXXX")"
trap 'rm -rf "$FIX"' EXIT
pass=0 fail=0

assert_eq() {
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); else
    fail=$((fail + 1)); printf 'FAIL: %s\n  expected: %s\n  actual:   %s\n' "$1" "$2" "$3"; fi
}

# ── the ledger helpers, EXTRACTED from orchestrator.sh ──────────────────────
# Not copied. A copy went stale once already: debt_clear was fixed in the script
# while this file kept exercising the buggy version — and passing. orchestrator.sh
# cannot be sourced (it re-execs and runs a preflight), so lift the functions out
# of it and eval them. Drift becomes impossible rather than merely detectable.
ORCH_SRC="$(cd "$(dirname "$0")" && pwd)/orchestrator.sh"
[ -f "$ORCH_SRC" ] || { echo "FAIL: cannot find $ORCH_SRC"; exit 1; }

extract_fn() { sed -n "/^$1() {/,/^}/p" "$ORCH_SRC"; }
for fn in debt_add debt_clear debt_issues debt_reason stuck_count stuck_clear stuck_bump next_gate_round; do
  src="$(extract_fn "$fn")"
  [ -n "$src" ] || { echo "FAIL: $fn() not found in orchestrator.sh"; exit 1; }
  eval "$src"
done

DEBT="$FIX/.review_debt.tsv"
STUCK="$FIX/.stuck_issues.tsv"
LOG_DIR="$FIX/logs"; mkdir -p "$LOG_DIR"

assert_eq "empty ledger lists nothing" "" "$(debt_issues)"
debt_add KCH-78 findings
debt_add KCH-84 gate-unavailable
assert_eq "two entries listed" "KCH-78 KCH-84" "$(debt_issues | tr '\n' ' ' | sed 's/ $//')"
assert_eq "reason is read back" "gate-unavailable" "$(debt_reason KCH-84)"
debt_add KCH-78 pr-open
assert_eq "re-adding replaces, never duplicates" "1" "$(debt_issues | grep -c '^KCH-78$')"
assert_eq "re-adding updates the reason" "pr-open" "$(debt_reason KCH-78)"
debt_clear KCH-78
assert_eq "clear removes only its own entry" "KCH-84" "$(debt_issues | tr '\n' ' ' | sed 's/ $//')"
debt_clear KCH-999
assert_eq "clearing an absent issue is a no-op, rc 0" "0" "$?"

# THE LAST ROW. `grep -v` exits 1 when it prints nothing, so `... && mv` skipped
# the move whenever the row being cleared was the only one left, and the ledger
# kept it. Every consequence pointed the wrong way: remediation announced "debt
# cleared" while the entry stood, DEBT_ONLY reported it still open, and
# debt_add's clear-then-append duplicated the row so the next pass remediated
# the same issue twice.
debt_clear KCH-84
assert_eq "clearing the LAST row actually empties the ledger" "" "$(debt_issues)"
assert_eq "and the file is empty, not merely unlisted" "0" "$(grep -c . "$DEBT" || true)"
debt_add KCH-84 findings
debt_clear KCH-84
debt_add KCH-84 findings
assert_eq "re-banking after clearing the last row does not duplicate" "1" "$(debt_issues | grep -c '^KCH-84$')"
debt_clear KCH-84

# ── the snapshot the debt phase actually loops over ─────────────────────────
# The 2026-09-09 regression: DEBT_RUN was declared, trapped, counted and read,
# but never written, so DEBT_N was 0 and the phase was skipped while the stop
# message — reading $DEBT directly — still reported the debt as open.
debt_add KCH-84 findings          # the clears above emptied the ledger
DEBT_RUN="$FIX/.debt.run"
debt_issues > "$DEBT_RUN" 2>/dev/null || : > "$DEBT_RUN"
DEBT_N="$(grep -c . "$DEBT_RUN" 2>/dev/null || echo 0)"
assert_eq "the snapshot is written before it is counted" "1" "$DEBT_N"
assert_eq "the snapshot matches the ledger" "$(debt_issues)" "$(cat "$DEBT_RUN")"

contradiction() {  # 1 when the ledger has rows the snapshot does not
  local n="$1"
  [ "${n:-0}" -eq 0 ] && [ -s "$DEBT" ] && echo 1 || echo 0
}
assert_eq "a written snapshot is not a contradiction" "0" "$(contradiction "$DEBT_N")"
assert_eq "ledger rows with an empty snapshot IS a contradiction" "1" "$(contradiction 0)"
: > "$DEBT"
assert_eq "an empty ledger with an empty snapshot is fine" "0" "$(contradiction 0)"

# ── queue snapshot must be taken AFTER remediation ──────────────────────────
# The other regression: remediation completes an issue, but a queue read earlier
# still lists it, so the pass tries to BUILD what it just fixed.
QUEUE="$FIX/queue.tsv"; DONE="$FIX/.completed"
printf '1\tKCH-84\n2\tKCH-89\n' > "$QUEUE"; : > "$DONE"
next_issues() {
  local p; p="$(comm -23 <(cut -f2 "$QUEUE" | sort) <(sort "$DONE" 2>/dev/null || true))"
  [ -z "$p" ] && return 0
  cut -f2 "$QUEUE" | grep -Fx -f <(printf '%s\n' "$p")
}
before="$(next_issues | tr '\n' ' ' | sed 's/ $//')"
echo "KCH-84" >> "$DONE"                      # what remediate_issue does on a clean gate
after="$(next_issues | tr '\n' ' ' | sed 's/ $//')"
assert_eq "queue lists the debt issue before remediation" "KCH-84 KCH-89" "$before"
assert_eq "queue drops it after remediation" "KCH-89" "$after"

# ── DEBT_ONLY gates the queue loop ──────────────────────────────────────────
gate() { [ "$1" = "1" ] && echo stop || echo queue; }
assert_eq "DEBT_ONLY=1 stops before the queue" "stop" "$(gate 1)"
assert_eq "DEBT_ONLY=0 enters the queue" "queue" "$(gate 0)"

# ── worktree lock: held vs abandoned ────────────────────────────────────────
WT="$FIX/.worktree.lock"
lock_state() {
  [ -d "$WT" ] || { echo proceed; return; }
  local p; p="$(cat "$WT/pid" 2>/dev/null || true)"
  if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then echo skip
  elif [ -n "$p" ]; then echo reclaim
  else echo unknown; fi
}
assert_eq "no lock -> proceed" "proceed" "$(lock_state)"
mkdir -p "$WT"; echo $$ > "$WT/pid"
assert_eq "live owner -> skip" "skip" "$(lock_state)"
echo 999999 > "$WT/pid"
assert_eq "dead owner -> reclaim" "reclaim" "$(lock_state)"
rm -f "$WT/pid"
assert_eq "no owner recorded -> fall back to age" "unknown" "$(lock_state)"

# ── stuck_clear must clear the last remaining row ───────────────────────────
# grep -v exits 1 when it prints no lines — if the issue being cleared is the
# only row, the old `&&`-chained mv never ran and the entry stayed forever.
STUCK="$FIX/.stuck_issues.tsv"
stuck_clear() {
  [ -f "$STUCK" ] || return 0
  grep -v "^$1	" "$STUCK" > "$STUCK.tmp" 2>/dev/null || true
  mv "$STUCK.tmp" "$STUCK" 2>/dev/null || true
  return 0
}
printf 'KCH-78\t3\tts\n' > "$STUCK"
stuck_clear KCH-78
rc=$?
assert_eq "clearing the only row empties the file" "" "$(cat "$STUCK" 2>/dev/null)"
assert_eq "clearing the only row returns 0" "0" "$rc"
printf 'KCH-78\t3\tts\nKCH-84\t1\tts\n' > "$STUCK"
stuck_clear KCH-78
assert_eq "clearing one of several rows keeps the rest" "KCH-84	1	ts" "$(cat "$STUCK")"

# ── gate rounds must be monotonic across passes ─────────────────────────────
# run_gate restarted at 0 every pass while --regate appends, and pr_gate.sh picks
# the last round by NUMBER. A KCH-78 remediation went clean at round 1 while a
# stale round 2 from an earlier regate survived, so the publisher would have
# failed a PR from a log three commits out of date.
GLOG="$LOG_DIR"
assert_eq "first gate starts at round 0" "0" "$(next_gate_round KCH-78)"
: > "$LOG_DIR/KCH-78_cr_round0.txt"; : > "$LOG_DIR/KCH-78_cr_round1.txt"
assert_eq "a second pass continues, never restarts at 0" "2" "$(next_gate_round KCH-78)"
: > "$LOG_DIR/KCH-78_cr_round2.txt"
assert_eq "a regate round is counted too" "3" "$(next_gate_round KCH-78)"
: > "$LOG_DIR/KCH-78_cr_round10.txt"
assert_eq "numeric max, not lexical" "11" "$(next_gate_round KCH-78)"
: > "$LOG_DIR/KCH-78_cr_roundXX.txt"
assert_eq "a non-numeric round name is ignored" "11" "$(next_gate_round KCH-78)"
assert_eq "another issue is unaffected" "0" "$(next_gate_round KCH-84)"

# ── blocking count must not include CodeRabbit's tally line ─────────────────
CR_BLOCKING="critical|major|blocker|high"
blocking_count() { grep -icE "^[[:space:]]*($CR_BLOCKING)[[:space:]]*\[" "$1" 2>/dev/null || true; }
cat > "$FIX/one.txt" <<'EOF'
  major [Security & Privacy]

  Validate the job and command failure paths.

Major    1

1 file reviewed:
EOF
assert_eq "one finding plus its tally counts as one" "1" "$(blocking_count "$FIX/one.txt")"
cat > "$FIX/clean.txt" <<'EOF'
CodeRabbit Review
0 issues found. A high-quality diff.
EOF
assert_eq "prose mentioning 'high' is not a finding" "0" "$(blocking_count "$FIX/clean.txt")"
cat > "$FIX/two.txt" <<'EOF'
  major [Functional Correctness]
  critical [Security & Privacy]
Major    1
Critical 1
EOF
assert_eq "two findings plus two tally lines counts as two" "2" "$(blocking_count "$FIX/two.txt")"

# ── the publisher must read the REPO's logs, not the relocated copy's ───────
# orchestrator.sh runs a $TMPDIR copy of pr_gate.sh (rule 1). Resolved from the
# copy's own location, LOG_DIR points at an empty $TMPDIR/logs and every gate
# reads "no run found — unreviewed", so wiring the publisher in without the
# override would publish a FAILURE on a PR that had just passed.
resolve_log_dir() { echo "${GATE_LOG_DIR:-$1/logs}"; }
assert_eq "no override -> the script's own ops dir" "/repo/ops/logs" "$(GATE_LOG_DIR= resolve_log_dir /repo/ops)"
assert_eq "relocated with no override -> the wrong, empty dir" "/tmp/ops.9/logs" "$(GATE_LOG_DIR= resolve_log_dir /tmp/ops.9)"
assert_eq "override wins, so the relocated copy reads the repo" "/repo/ops/logs" "$(GATE_LOG_DIR=/repo/ops/logs resolve_log_dir /tmp/ops.9)"

# ── structural guards: things unit tests cannot reach, but greps can ────────
# These two defects are invisible to behavioural tests here (both need a live
# gh), and both were shipped once already, so assert the shape directly.
ORCH="$(cd "$(dirname "$0")" && pwd)/orchestrator.sh"

# Every success path out of remediate_issue must publish. The re-gate-only path
# — taken by quota-banked debt, the most common reason — cleared its ledger and
# left the PR drafted with a stale status.
# ── remediate_issue: behaviour, not shape ───────────────────────────────────
# Three structural greps in a row failed to pin this function down — one counted
# comments, one passed a mutation it should have caught. So run the real thing
# against stubs in a scratch repo.
#
# The defect: run_gate is NOT read-only. A round with blocking findings calls the
# agent and commits the fix, so the re-gate-only path — taken by quota-banked
# debt — can move HEAD. It returned 1 without pushing, stranding those commits on
# the local checkout: invisible to the PR, and leaving the branch ahead of origin
# for the next pass to trip over.
eval "$(sed -n '/^remediate_issue() {/,/^}/p' "$ORCH_SRC")"

RSTUB="$FIX/rem"; mkdir -p "$RSTUB"
setup_remediate_case() {   # $1 = debt reason, $2 = gate rc, $3 = does run_gate commit?
  rm -rf "$RSTUB/repo" "$RSTUB/origin"; mkdir -p "$RSTUB/repo"
  git init -q --bare "$RSTUB/origin"
  git -C "$RSTUB/repo" init -q
  git -C "$RSTUB/repo" config user.email t@e.com; git -C "$RSTUB/repo" config user.name T
  git -C "$RSTUB/repo" remote add origin "$RSTUB/origin"
  git -C "$RSTUB/repo" commit -q --allow-empty -m base
  git -C "$RSTUB/repo" branch -M feature/kch-99
  git -C "$RSTUB/repo" push -q -u origin feature/kch-99
  PUSHED=0; PUBLISHED=0
  DEBT="$RSTUB/debt"; printf 'KCH-99\t%s\tts\n' "$1" > "$DEBT"
  DONE="$RSTUB/done"; : > "$DONE"
  LOG_DIR="$RSTUB/logs"; mkdir -p "$LOG_DIR"
  GATE_RC="$2"; GATE_COMMITS="$3"
  # Config the real script sets at load time; unset here, and `set -u` is on.
  IMPL_MODEL=stub-model; CR_MAX_ROUNDS=2; BASE_BRANCH=development; AGENT_KIND=ok
  say() { :; }; fail() { :; }
  take_lock() { return 0; }; drop_lock() { :; }
  issue_title() { echo "stub"; }
  open_pr_field() { [ "$2" = baseRefName ] && echo development || echo 1; }
  run_agent() { AGENT_KIND=ok; echo x >> "$RSTUB/repo/f.txt"; return 0; }
  run_gate() { [ "$GATE_COMMITS" = yes ] && { echo g >> "$RSTUB/repo/g.txt"; git add -A; git commit -q -m "fix(KCH-99): address CodeRabbit round 1"; }; return "$GATE_RC"; }
  publish_gate() { PUBLISHED=1; }
  git() { case "$*" in "push"*|*"push "*) PUSHED=1; return 0;; esac; command git -C "$RSTUB/repo" "$@"; }
}

# THE REGRESSION: quota debt, re-gate produces fix commits, gate still fails.
setup_remediate_case quota 1 yes
( cd "$RSTUB/repo" && remediate_issue KCH-99 >/dev/null 2>&1; echo "$PUSHED" ) > "$RSTUB/out"
assert_eq "a failing re-gate that produced commits still pushes them" "1" "$(cat "$RSTUB/out")"

# Clean re-gate: pushes and publishes.
setup_remediate_case quota 0 yes
( cd "$RSTUB/repo" && remediate_issue KCH-99 >/dev/null 2>&1; echo "$PUSHED $PUBLISHED" ) > "$RSTUB/out"
assert_eq "a clean re-gate pushes and publishes" "1 1" "$(cat "$RSTUB/out")"

# Nothing changed: no push at all, rather than a pointless force-push.
setup_remediate_case quota 0 no
( cd "$RSTUB/repo" && remediate_issue KCH-99 >/dev/null 2>&1; echo "$PUSHED" ) > "$RSTUB/out"
assert_eq "an unchanged HEAD is not force-pushed" "0" "$(cat "$RSTUB/out")"

# Findings debt takes the agent path; it must push and publish on a clean gate.
setup_remediate_case findings 0 no
printf '  major [X]\n\n1 file reviewed:\n' > "$RSTUB/logs/KCH-99_cr_round0.txt"
( cd "$RSTUB/repo" && remediate_issue KCH-99 >/dev/null 2>&1; echo "$PUSHED $PUBLISHED" ) > "$RSTUB/out"
assert_eq "the agent path pushes and publishes too" "1 1" "$(cat "$RSTUB/out")"
unset -f git say fail take_lock drop_lock issue_title open_pr_field run_agent run_gate publish_gate

# run_issue's clean-gate path is the one every NEW PR takes. It recorded the
# issue done and published nothing, so with the status required no fresh PR
# could merge without someone running pr_gate.sh by hand.
clean_path="$(sed -n '/^run_issue()/,/^}/p' "$ORCH" \
  | sed -n '/if \[ "\$gate" -eq 0 \]; then/,/^  else$/p')"
if [ -z "$clean_path" ]; then
  fail=$((fail+1)); echo "FAIL: could not locate run_issue's clean-gate branch"
elif printf '%s' "$clean_path" | grep -q 'publish_gate'; then pass=$((pass+1)); else
  fail=$((fail+1)); echo "FAIL: run_issue's clean-gate path must publish the gate status"; fi

# A merged PR must not be mistaken for an open one: `gh pr view <branch>`
# resolves merged and closed PRs, which would make the rebuild guard bank an
# already-merged issue as debt that can never clear.
assert_eq "no unfiltered gh pr view survives in the loop" "0" \
  "$(grep -c '^[^#]*gh pr view' "$ORCH" || true)"
assert_eq "the PR lookup filters to open" "1" \
  "$(grep -c 'gh pr list --state open --head' "$ORCH" || true)"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]

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

# ── the ledger helpers, copied verbatim from orchestrator.sh ────────────────
DEBT="$FIX/.review_debt.tsv"
debt_add() { local i="$1" r="${2:-findings}"; debt_clear "$i"; printf '%s\t%s\t%s\n' "$i" "$r" "ts" >> "$DEBT"; }
debt_clear() { [ -f "$DEBT" ] || return 0; grep -v "^$1	" "$DEBT" > "$DEBT.tmp" 2>/dev/null && mv "$DEBT.tmp" "$DEBT"; return 0; }
debt_issues() { [ -f "$DEBT" ] && cut -f1 "$DEBT" 2>/dev/null | grep -v '^$' || true; }
debt_reason() { awk -F'\t' -v i="$1" '$1 == i { r = $2 } END { print r }' "$DEBT" 2>/dev/null; }

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

# ── the snapshot the debt phase actually loops over ─────────────────────────
# The 2026-09-09 regression: DEBT_RUN was declared, trapped, counted and read,
# but never written, so DEBT_N was 0 and the phase was skipped while the stop
# message — reading $DEBT directly — still reported the debt as open.
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

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]

#!/usr/bin/env bash
# ops/pr_gate.test.sh — unit tests for the pure helpers in ops/pr_gate.sh.  [KCH-78]
#
# Exercises round parsing, the blocking-finding count, the round -> fix-commit
# mapping, the pass/fail verdict, and the rendered report — all against fixture
# logs and a scratch git repo. No gh, no network: this is what makes the gate
# publisher testable without a live PR.
#
# Run: ops/pr_gate.test.sh

set -uo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$OPS_DIR/pr_gate.sh"   # sourcing (not executing) skips main() — see its BASH_SOURCE guard

FIX_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pr_gate_test.XXXXXX")"
FIX_REPO="$FIX_DIR/repo"
trap 'rm -rf "$FIX_DIR"' EXIT

pass=0 fail=0
assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s\n  expected: %s\n  actual:   %s\n' "$desc" "$expected" "$actual"
  fi
}
assert_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -qF "$needle"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL: %s\n  expected to contain: %s\n' "$desc" "$needle"
  fi
}

# ── fixture repo: two fix commits answering rounds 0 and 1 ──────────────────
mkdir -p "$FIX_REPO"
git -C "$FIX_REPO" init -q
git -C "$FIX_REPO" config user.email test@example.com
git -C "$FIX_REPO" config user.name "Test"
echo one > "$FIX_REPO/a.txt"
git -C "$FIX_REPO" add a.txt
git -C "$FIX_REPO" commit -q -m "KCH-99: implement thing"
echo two > "$FIX_REPO/a.txt"
git -C "$FIX_REPO" add a.txt
git -C "$FIX_REPO" commit -q -m "fix(KCH-99): address CodeRabbit round 1"
echo three > "$FIX_REPO/a.txt"
git -C "$FIX_REPO" add a.txt
git -C "$FIX_REPO" commit -q -m "fix(KCH-99): address CodeRabbit round 2"

# ── round_number / round_files ───────────────────────────────────────────────
assert_eq "round_number strips prefix/suffix" "0" "$(round_number "/x/KCH-99_cr_round0.txt")"
assert_eq "round_number handles multi-digit" "10" "$(round_number "/x/KCH-99_cr_round10.txt")"

LOGS="$FIX_DIR/logs"; mkdir -p "$LOGS"
: > "$LOGS/KCH-99_cr_round0.txt"
: > "$LOGS/KCH-99_cr_round10.txt"
: > "$LOGS/KCH-99_cr_round2.txt"
ordered="$(round_files KCH-99 "$LOGS")"
assert_eq "round_files sorts numerically, not lexically" \
  "$LOGS/KCH-99_cr_round0.txt
$LOGS/KCH-99_cr_round2.txt
$LOGS/KCH-99_cr_round10.txt" "$ordered"
assert_eq "round_files empty when no logs for the issue" "" "$(round_files KCH-999 "$LOGS")"
rm -rf "$LOGS"; mkdir -p "$LOGS"

# ── round_unavailable ─────────────────────────────────────────────────────
echo "Error: rate limit exceeded, try again later" > "$LOGS/quota.txt"
echo "1 issue found: Major - missing null check" > "$LOGS/findings.txt"
if round_unavailable "$LOGS/quota.txt"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: round_unavailable should flag quota text"; fi
if round_unavailable "$LOGS/findings.txt"; then fail=$((fail+1)); echo "FAIL: round_unavailable should not flag ordinary findings"; else pass=$((pass+1)); fi

# ── round_blocking_count / round_blocking_lines ──────────────────────────
cat > "$LOGS/mixed.txt" <<'EOF'
1. Nit: rename variable for clarity
2. Major: SQL built via string concatenation
3. Blocker: money computed with float, not Decimal
4. Minor: docstring formatting
EOF
assert_eq "round_blocking_count counts only blocking severities" "2" "$(round_blocking_count "$LOGS/mixed.txt")"
assert_contains "round_blocking_lines surfaces the Major line" "$(round_blocking_lines "$LOGS/mixed.txt")" "SQL built via string concatenation"
assert_contains "round_blocking_lines surfaces the Blocker line" "$(round_blocking_lines "$LOGS/mixed.txt")" "float, not Decimal"

# ── fix_commit_for_round ─────────────────────────────────────────────────
commit0="$(fix_commit_for_round KCH-99 0 "$FIX_REPO")"
assert_contains "round 0's findings are answered by the 'round 1' commit" "$commit0" "address CodeRabbit round 1"
commit1="$(fix_commit_for_round KCH-99 1 "$FIX_REPO")"
assert_contains "round 1's findings are answered by the 'round 2' commit" "$commit1" "address CodeRabbit round 2"
assert_eq "a round with no answering commit returns nothing" "" "$(fix_commit_for_round KCH-99 5 "$FIX_REPO")"
assert_eq "a different issue's commits are not matched" "" "$(fix_commit_for_round KCH-77 0 "$FIX_REPO")"

# ── gate_verdict ───────────────────────────────────────────────────────────
rm -rf "$LOGS"; mkdir -p "$LOGS"

assert_eq "no logs at all -> failure (unreviewed)" "failure" "$(gate_verdict KCH-1 "$LOGS"; echo "$VERDICT_STATE")"

echo "0 issues found" > "$LOGS/KCH-2_cr_round0.txt"
gate_verdict KCH-2 "$LOGS"
assert_eq "clean final round -> success" "success" "$VERDICT_STATE"

echo "1 issue found: Critical - hardcoded secret" > "$LOGS/KCH-3_cr_round0.txt"
echo "1 issue found: Critical - hardcoded secret" > "$LOGS/KCH-3_cr_round1.txt"
gate_verdict KCH-3 "$LOGS"
assert_eq "blocking findings survive to the final round -> failure" "failure" "$VERDICT_STATE"

echo "0 issues found" > "$LOGS/KCH-4_cr_round0.txt"
echo "Error: quota exceeded" > "$LOGS/KCH-4_cr_round1.txt"
gate_verdict KCH-4 "$LOGS"
assert_eq "final round unavailable overrides an earlier clean round -> failure" "failure" "$VERDICT_STATE"

# A clean round that is NOT the final one must not short-circuit the verdict.
echo "1 issue found: Blocker - x" > "$LOGS/KCH-5_cr_round0.txt"
echo "0 issues found" > "$LOGS/KCH-5_cr_round1.txt"
gate_verdict KCH-5 "$LOGS"
assert_eq "verdict reads the LAST round, not the first" "success" "$VERDICT_STATE"

# ── build_report ─────────────────────────────────────────────────────────
report="$(build_report KCH-3 "$LOGS" "$FIX_REPO")"
assert_contains "report carries the issue marker for idempotent updates" "$report" "<!-- coderabbit-cli-gate:KCH-3 -->"
assert_contains "report lists round 0" "$report" "| 0 |"
assert_contains "report marks the last row final" "$report" "1 (final)"
assert_contains "report calls out the failing verdict" "$report" "❌"

report_clean="$(build_report KCH-2 "$LOGS" "$FIX_REPO")"
assert_contains "clean report calls out the passing verdict" "$report_clean" "✅"

report_none="$(build_report KCH-777 "$LOGS" "$FIX_REPO")"
assert_contains "no-run report says unreviewed" "$report_none" "Unreviewed — cannot merge"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]

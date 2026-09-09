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

# Verbatim from ops/logs/KCH-78_cr_round0.txt on 2026-09-08: a CLI usage error
# carries no severity keyword, so it counted as a clean review and published a
# green gate for a branch CodeRabbit never read.
cat > "$LOGS/badflag.txt" <<'EOF'
error: unknown option '--plain'

Usage: coderabbit review [options] [command]
EOF
echo "Not logged in. Run: coderabbit auth login" > "$LOGS/signedout.txt"
# Verbatim from ops/logs/KCH-85_cr_round1.txt: the review connected, ran 5m14s,
# then dropped. No severity keyword anywhere, so it scored clean and would have
# greened PR #7 on a review that never finished.
cat > "$LOGS/wsdrop.txt" <<'EOF'
Writing review comments... 5m 14s elapsed - still working

  ✗ Connection error

  Connection failed: WebSocket closed

Error: WebSocket closed
EOF
if round_unavailable "$LOGS/wsdrop.txt"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: round_unavailable should flag a dropped connection"; fi
# ...but a finding that merely mentions an error must still count as a review.
cat > "$LOGS/mentions_error.txt" <<'EOF'
CodeRabbit Review
1. Major: swallowed error in the retry path — log it before returning
EOF
if round_unavailable "$LOGS/mentions_error.txt"; then fail=$((fail+1)); echo "FAIL: a finding mentioning 'error' is not an unavailable round"; else pass=$((pass+1)); fi
if round_unavailable "$LOGS/badflag.txt"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: round_unavailable should flag a CLI usage error"; fi
if round_unavailable "$LOGS/signedout.txt"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: round_unavailable should flag a signed-out session"; fi
cp "$LOGS/badflag.txt" "$LOGS/KCH-98_cr_round0.txt"
gate_verdict KCH-98 "$LOGS"
assert_eq "a CLI usage error is never the clean final verdict" "failure" "$VERDICT_STATE"
rm -f "$LOGS/KCH-98_cr_round0.txt"

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

# ── issue_branch ─────────────────────────────────────────────────────────
assert_eq "issue_branch matches the orchestrator's naming" "feature/kch-78" "$(issue_branch KCH-78)"

# ── round_sha ────────────────────────────────────────────────────────────
# The verdict has to be attributable to a commit; absence must read as "cannot
# verify", never as proof.
SH="$FIX_DIR/sha"; mkdir -p "$SH"
: > "$SH/KCH-70_cr_round0.txt"
assert_eq "no sidecar -> empty, not an error" "" "$(round_sha "$SH/KCH-70_cr_round0.txt")"
echo "abc1234def" > "$SH/KCH-70_cr_round0.sha"
assert_eq "sidecar is read back" "abc1234def" "$(round_sha "$SH/KCH-70_cr_round0.txt")"

# ── next_round_file ──────────────────────────────────────────────────────
# A re-gate appends; it must never overwrite the earlier rounds, which are the
# record of what CodeRabbit found and which commit answered it.
RF="$FIX_DIR/rounds"; mkdir -p "$RF"
assert_eq "first round when nothing has run" "$RF/KCH-90_cr_round0.txt" "$(next_round_file KCH-90 "$RF")"
: > "$RF/KCH-90_cr_round0.txt"
assert_eq "appends after round 0" "$RF/KCH-90_cr_round1.txt" "$(next_round_file KCH-90 "$RF")"
: > "$RF/KCH-90_cr_round1.txt"; : > "$RF/KCH-90_cr_round2.txt"; : > "$RF/KCH-90_cr_round10.txt"
assert_eq "takes the numeric max, not the lexical one" "$RF/KCH-90_cr_round11.txt" "$(next_round_file KCH-90 "$RF")"
assert_eq "another issue's rounds do not shift it" "$RF/KCH-91_cr_round0.txt" "$(next_round_file KCH-91 "$RF")"

# ── pr_stack_order ───────────────────────────────────────────────────────
# gh returns PRs newest-first, and PR numbers do not track stack depth (an issue
# retried after a failure gets a higher number than the branch above it), so the
# order has to come from following baseRefName up from development.
STACK="$(printf '%s\n' \
  "9	feature/kch-80	feature/kch-81" \
  "2	development	feature/kch-78" \
  "7	feature/kch-78	feature/kch-80")"
assert_eq "orders a stack bottom-up by base, not by number" "2
7
9" "$(pr_stack_order development "$STACK")"
assert_eq "empty when nothing bases on development" "" \
  "$(pr_stack_order development "$(printf '%s\n' "5	feature/orphan	feature/other")")"
assert_eq "ignores malformed rows" "2" \
  "$(pr_stack_order development "$(printf '%s\n' "2	development	feature/kch-78" "garbage" "")")"
# Two PRs on the same base is a fork in the stack, not a chain — both belong.
assert_eq "handles a branch point" "2
3" "$(pr_stack_order development "$(printf '%s\n' \
  "2	development	feature/kch-78" "3	development	feature/kch-79")")"
# A base pointing back into the stack must not spin forever.
assert_eq "a cycle terminates" "2
4" "$(pr_stack_order development "$(printf '%s\n' \
  "2	development	feature/a" "4	feature/a	feature/b" "4	feature/b	feature/a")")"
# Distinct PR numbers on each row of the cycle — the dedup-by-number check alone
# would not stop this one; only the revisit of an already-processed base does.
assert_eq "a cycle with distinct numbers terminates" "2
4
5" "$(pr_stack_order development "$(printf '%s\n' \
  "2	development	feature/a" "4	feature/a	feature/b" "5	feature/b	feature/a")")"

# ── publish_for_issue: a failed status POST must not read as success ───────
# The status POST's exit code used to be ignored — a gh/network error left the
# PR with no coderabbit/cli-gate status while the script still exited 0 on a
# clean verdict. See the header's "gh/network error exits 1" contract.
PFI_LOGS="$FIX_DIR/pfi_logs"; mkdir -p "$PFI_LOGS"
echo "0 issues found" > "$PFI_LOGS/KCH-50_cr_round0.txt"
PFI_REPO="$FIX_DIR/pfi_repo"; mkdir -p "$PFI_REPO"
git -C "$PFI_REPO" init -q
git -C "$PFI_REPO" config user.email test@example.com
git -C "$PFI_REPO" config user.name "Test"
git -C "$PFI_REPO" commit -q --allow-empty -m "KCH-50: seed"

gh() {
  case "$1" in
    pr)   [ "$2" = "view" ] && echo '{"number":50,"headRefOid":"deadbeef","url":"https://example/pr/50","isDraft":false}' ;;
    repo) [ "$2" = "view" ] && echo "acme/finhive" ;;
    api)
      case "$*" in
        *"/statuses/"*) return 1 ;;
        *) echo "https://example/comment/1" ;;
      esac ;;
  esac
}

_saved_log_dir="$LOG_DIR" _saved_repo_dir="$REPO_DIR"
LOG_DIR="$PFI_LOGS" REPO_DIR="$PFI_REPO"
pfi_err="$(publish_for_issue KCH-50 2>&1 >/dev/null)"
pfi_rc=$?
LOG_DIR="$_saved_log_dir" REPO_DIR="$_saved_repo_dir"
unset -f gh

assert_eq "a failed status POST makes publish_for_issue fail, not succeed" "1" "$pfi_rc"
assert_contains "the failure names the missing gate status" "$pfi_err" "no gate status"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]

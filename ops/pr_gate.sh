#!/usr/bin/env bash
# ops/pr_gate.sh — publishes the CLI gate's findings trail per PR.  [KCH-78]
#
# ops/orchestrator.sh runs the CodeRabbit CLI gate PRE-PUSH (see run_gate()) so a
# PR's fix commits are already in its first commit set. That leaves the gate's
# result sitting only in ops/logs/*.txt — gitignored, local, and from GitHub's
# side an unverifiable claim with no check behind it.
#
# This script re-publishes that trail on the PR itself and sets a
# coderabbit/cli-gate commit status, so the claim has evidence a human (or a
# branch protection rule) can see without shelling into the machine that ran it:
#   - every round's blocking findings
#   - the commit that answered each round (round N is fixed by the commit
#     tagged "round N+1" — see run_gate(), which commits before re-running)
#   - the final round's re-review verdict
#
# The status is success only when the FINAL round returned zero blocking
# findings. No logs at all (never gated) or a final round that errored/hit
# quota (never actually reviewed) both count as failure, not success — an
# unreviewed branch must not read as a clean one.
#
# No Claude here by design: bash + git + gh + the logs already on disk. This
# has to work even when a spend cap has stopped the builder.
#
# Usage:
#   ops/pr_gate.sh ISSUE              publish findings + set status for ISSUE's PR
#   ops/pr_gate.sh --require-check    make coderabbit/cli-gate required on development
#
# Exit status mirrors the gate verdict: 0 when the final round is clean, 1 otherwise
# (including "no run found" and "gh/network error") — so it can drive CI directly.

set -uo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$OPS_DIR/.." && pwd)"
LOG_DIR="$OPS_DIR/logs"

CR_BLOCKING="${CR_BLOCKING:-critical|major|blocker|high}"
GATE_CONTEXT="${GATE_CONTEXT:-coderabbit/cli-gate}"
BASE_BRANCH="${BASE_BRANCH:-development}"
MARKER_PREFIX="<!-- coderabbit-cli-gate:"

say()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }

# ── pure helpers — no gh, no network; unit-tested directly ──────────────────

# Round number embedded in a gate log's filename, e.g. "0" from
# ".../KCH-78_cr_round0.txt".
round_number() {
  local base
  base="$(basename "$1")"
  base="${base#*_cr_round}"
  printf '%s' "${base%.txt}"
}

# An issue's round logs, oldest first. Numeric sort: plain `sort` on the
# filename puts "round10" before "round2".
round_files() {
  local issue="$1" dir="${2:-$LOG_DIR}"
  local f n
  for f in "$dir/${issue}_cr_round"*.txt; do
    [ -e "$f" ] || continue
    n="$(round_number "$f")"
    printf '%s\t%s\n' "$n" "$f"
  done | sort -n -k1,1 | cut -f2
}

# A round that errored or hit CodeRabbit's quota never actually reviewed the
# diff — it must not be read as clean just because it has no blocking lines.
round_unavailable() {
  grep -qiE 'rate.?limit|quota|too many requests' "$1" 2>/dev/null
}

round_blocking_count() { grep -icE "$CR_BLOCKING" "$1" 2>/dev/null || true; }
round_blocking_lines() { grep -iE "$CR_BLOCKING" "$1" 2>/dev/null || true; }

# ops/orchestrator.sh's run_gate() commits the fix BEFORE re-running the gate
# as the next round, so round N's findings are answered by the commit tagged
# "round N+1", not "round N". The final round (clean, or escalated after
# CR_MAX_ROUNDS) never gets a following commit.
fix_commit_for_round() {
  local issue="$1" round="$2" repo="${3:-$REPO_DIR}"
  git -C "$repo" log --format='%h %s' -E \
    --grep="^fix\\($issue\\): address CodeRabbit round $((round + 1))\$" \
    2>/dev/null | head -1
}

# Sets VERDICT_STATE (success|failure) and VERDICT_DESC.
gate_verdict() {
  local issue="$1" dir="${2:-$LOG_DIR}"
  local files; files="$(round_files "$issue" "$dir")"
  if [ -z "$files" ]; then
    VERDICT_STATE="failure"
    VERDICT_DESC="no CodeRabbit CLI gate run found — unreviewed branch"
    return
  fi
  local last; last="$(printf '%s\n' "$files" | tail -1)"
  if round_unavailable "$last"; then
    VERDICT_STATE="failure"
    VERDICT_DESC="gate unavailable on the final round (quota/error) — unreviewed"
    return
  fi
  local blocking; blocking="$(round_blocking_count "$last")"
  if [ "${blocking:-0}" -eq 0 ]; then
    VERDICT_STATE="success"
    VERDICT_DESC="clean — 0 blocking findings on the final round"
  else
    VERDICT_STATE="failure"
    VERDICT_DESC="$blocking blocking finding(s) survived the final round"
  fi
}

# Markdown findings trail for one issue: a round/commit table, the blocking
# lines for any round that had them, and the verdict. Starts with a hidden
# marker so publish_comment() can find and update the same comment next time.
build_report() {
  local issue="$1" dir="${2:-$LOG_DIR}" repo="${3:-$REPO_DIR}"
  local files; files="$(round_files "$issue" "$dir")"

  printf '%s%s -->\n' "$MARKER_PREFIX" "$issue"
  printf '## CodeRabbit CLI gate — %s\n\n' "$issue"

  if [ -z "$files" ]; then
    echo "No CLI gate run recorded for this branch. **Unreviewed — cannot merge.**"
    return
  fi

  local total; total="$(printf '%s\n' "$files" | grep -c .)"

  echo "| Round | Blocking findings | Answered by |"
  echo "|---|---|---|"
  local i=0
  printf '%s\n' "$files" | while IFS= read -r f; do
    local n label blocking commit
    i=$((i + 1))
    n="$(round_number "$f")"
    label="$n"; [ "$i" -eq "$total" ] && label="$n (final)"
    if round_unavailable "$f"; then
      echo "| $label | unavailable (quota/error) | — |"
      continue
    fi
    blocking="$(round_blocking_count "$f")"
    if [ "$i" -eq "$total" ]; then
      if [ "${blocking:-0}" -eq 0 ]; then
        echo "| $label | 0 | — clean |"
      else
        echo "| $label | $blocking | — unresolved, escalated |"
      fi
    else
      commit="$(fix_commit_for_round "$issue" "$n" "$repo")"
      echo "| $label | $blocking | \`${commit:-no commit found}\` |"
    fi
  done
  echo

  printf '%s\n' "$files" | while IFS= read -r f; do
    local n blocking
    n="$(round_number "$f")"
    round_unavailable "$f" && continue
    blocking="$(round_blocking_count "$f")"
    [ "${blocking:-0}" -eq 0 ] && continue
    echo "<details><summary>Round $n — $blocking blocking finding(s)</summary>"
    echo
    echo '```'
    round_blocking_lines "$f" | head -50
    echo '```'
    echo "</details>"
    echo
  done

  gate_verdict "$issue" "$dir"
  if [ "$VERDICT_STATE" = "success" ]; then
    echo "**Verdict:** ✅ $VERDICT_DESC"
  else
    echo "**Verdict:** ❌ $VERDICT_DESC"
  fi
}

# ── gh-facing side — network, mocked out in tests ────────────────────────────

LAST_COMMENT_URL=""

# Idempotent by the hidden marker: updates the same comment on re-publish
# (e.g. a later round) instead of piling up a new one per run.
publish_comment() {
  local repo_slug="$1" pr_number="$2" issue="$3" body="$4"
  local marker="${MARKER_PREFIX}${issue} -->"
  local existing_id
  existing_id="$(gh api "repos/$repo_slug/issues/$pr_number/comments" --paginate \
      -q ".[] | select(.body | startswith(\"$marker\")) | .id" 2>/dev/null | head -1)"
  if [ -n "$existing_id" ]; then
    LAST_COMMENT_URL="$(gh api "repos/$repo_slug/issues/comments/$existing_id" \
        -X PATCH -f body="$body" -q .html_url)"
  else
    LAST_COMMENT_URL="$(gh api "repos/$repo_slug/issues/$pr_number/comments" \
        -X POST -f body="$body" -q .html_url)"
  fi
}

# One-time repo-admin action, not part of the per-PR publish flow: adds this
# context to development's required status checks. Requires branch protection
# to already exist on development (this only appends a context to it).
require_check() {
  local repo_slug; repo_slug="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
  [ -n "$repo_slug" ] || { fail "could not resolve repo slug"; return 1; }
  say "Adding $GATE_CONTEXT as a required status check on $BASE_BRANCH ($repo_slug)"
  gh api "repos/$repo_slug/branches/$BASE_BRANCH/protection/required_status_checks/contexts" \
    -X POST -f "contexts[]=$GATE_CONTEXT"
}

usage() { echo "usage: $(basename "$0") ISSUE | --require-check" >&2; exit 2; }

main() {
  # shellcheck disable=SC1091
  [ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

  for t in git gh python3; do
    command -v "$t" >/dev/null 2>&1 || { fail "$t not found on PATH"; exit 1; }
  done

  case "${1:-}" in
    --require-check) require_check; exit $? ;;
    "" | --*) usage ;;
  esac
  local issue="$1"

  gh auth status >/dev/null 2>&1 || { fail "gh not authenticated — run: gh auth login"; exit 1; }

  local branch="feature/$(printf '%s' "$issue" | tr '[:upper:]' '[:lower:]')"
  local pr_json
  if ! pr_json="$(gh pr view "$branch" --json number,headRefOid,url 2>&1)"; then
    fail "no PR found for branch $branch — $pr_json"
    exit 1
  fi
  local pr_number pr_sha pr_url
  pr_number="$(printf '%s' "$pr_json" | python3 -c 'import json,sys;print(json.load(sys.stdin)["number"])' 2>/dev/null)"
  pr_sha="$(printf '%s' "$pr_json"    | python3 -c 'import json,sys;print(json.load(sys.stdin)["headRefOid"])' 2>/dev/null)"
  pr_url="$(printf '%s' "$pr_json"    | python3 -c 'import json,sys;print(json.load(sys.stdin)["url"])' 2>/dev/null)"
  [ -n "$pr_number" ] && [ -n "$pr_sha" ] || { fail "could not parse PR info for $branch"; exit 1; }

  local repo_slug; repo_slug="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"
  [ -n "$repo_slug" ] || { fail "could not resolve repo slug"; exit 1; }

  local report; report="$(build_report "$issue" "$LOG_DIR" "$REPO_DIR")"
  gate_verdict "$issue" "$LOG_DIR"

  publish_comment "$repo_slug" "$pr_number" "$issue" "$report"

  local gh_state; gh_state="failure"; [ "$VERDICT_STATE" = "success" ] && gh_state="success"
  gh api "repos/$repo_slug/statuses/$pr_sha" \
    -f state="$gh_state" \
    -f context="$GATE_CONTEXT" \
    -f description="$(printf '%s' "$VERDICT_DESC" | cut -c1-140)" \
    -f target_url="${LAST_COMMENT_URL:-$pr_url}" \
    >/dev/null

  say "PR #$pr_number ($issue): $GATE_CONTEXT = $gh_state — $VERDICT_DESC"
  [ "$VERDICT_STATE" = "success" ]
}

# Sourced by ops/pr_gate.test.sh to unit-test the pure helpers above without
# touching gh or the network; only run main() when executed directly.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi

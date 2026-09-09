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
# Clearing the draft on a clean gate is the default; --no-promote opts out.
# Defaulted here, not in main(), so sourcing this file for tests is safe under -u.
PROMOTE="${PROMOTE:-1}"

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
#
# Quota is not the only way a round can fail to happen. A CLI usage error
# ("unknown option '--plain'"), a signed-out session, or a dropped connection
# prints a help screen or a one-line hint and exits — text containing no severity
# keyword at all, which scored as "0 blocking findings" and published a green
# gate for a branch CodeRabbit never looked at. Treat every not-a-review outcome
# the same.
#
# The transport cases are not hypothetical: KCH-85 round 1 died on "Connection
# failed: WebSocket closed" after 5m14s and would have published a clean gate on
# a PR whose review never finished. `^Error:` is the generic backstop — the CLI
# ends a failed run with it, and anchoring to the line start keeps a finding that
# merely mentions an error from tripping it. Validated against all 17 gate logs
# on disk: flags exactly the three unreviewed rounds, no false positives.
round_unavailable() {
  grep -qiE '^[[:space:]]*Error:|rate.?limit|quota|too many requests|unknown option|unknown command|Usage: coderabbit|not logged in|unauthorized|authentication failed|connection error|connection failed|websocket closed' "$1" 2>/dev/null
}

# The commit a round reviewed, recorded beside its log by regate(). Empty for
# rounds the builder wrote (it gates pre-push, so there is no PR head to compare
# against yet) — absence means "cannot verify", never "verified".
round_sha() { [ -f "${1%.txt}.sha" ] && cat "${1%.txt}.sha" 2>/dev/null || true; }

round_blocking_count() { grep -icE "$CR_BLOCKING" "$1" 2>/dev/null || true; }
round_blocking_lines() { grep -iE "$CR_BLOCKING" "$1" 2>/dev/null || true; }

# The branch ops/orchestrator.sh names for an issue: feature/<issue lowercased>.
issue_branch() { printf 'feature/%s' "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"; }

# Where the NEXT round log for an issue goes. A re-gate must not overwrite the
# rounds the builder already wrote — those are the record of what was found and
# fixed. It appends a round; since gate_verdict reads the LAST round, the
# re-review is what decides the verdict.
next_round_file() {
  local issue="$1" dir="${2:-$LOG_DIR}" f n max=-1
  for f in $(round_files "$issue" "$dir"); do
    n="$(round_number "$f")"
    [ "$n" -gt "$max" ] && max="$n"
  done
  printf '%s/%s_cr_round%d.txt' "$dir" "$issue" "$((max + 1))"
}

# Bottom-up order for a stack of PRs, from "number<TAB>base<TAB>head" lines.
#
# A stacked PR's base is the branch below it, so the stack is a chain upward from
# BASE_BRANCH. That is neither the order gh returns nor PR-number order — an
# issue retried after a failure gets a higher number than the branch above it.
# Merging out of order conflicts, so this is what decides the walk.
pr_stack_order() {
  local base="$1" rows="$2"
  python3 -c '
import sys
base, rows = sys.argv[1], sys.argv[2]
by_base = {}
for line in rows.splitlines():
    parts = line.split("\t")
    if len(parts) != 3 or not parts[0].strip():
        continue
    num, b, head = (p.strip() for p in parts)
    by_base.setdefault(b, []).append((num, head))
out, seen, frontier = [], set(), [base]
while frontier:
    nxt = []
    for b in frontier:
        for num, head in sorted(by_base.get(b, [])):
            if num in seen:
                continue                 # a cycle would otherwise loop forever
            seen.add(num)
            out.append(num)
            nxt.append(head)
    frontier = nxt
print("\n".join(out))
' "$base" "$rows" 2>/dev/null
}

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

# Review a whole branch against BASE_BRANCH and append the result as a new round.
#
# The builder's own gate reviews each branch against the branch BELOW it, which is
# the right diff while building a stack but leaves the bottom PR's full contents
# never reviewed as a unit. This reviews everything the PR would merge.
#
# It runs in a throwaway detached worktree, never the shared checkout: the builder
# holds that one for hours and `coderabbit review` needs the branch checked out.
# Detached on purpose — claiming the branch would make the builder's own
# `git checkout` of it fail with "already used by worktree".
regate() {
  local issue="$1"
  local branch; branch="$(issue_branch "$issue")"
  command -v coderabbit >/dev/null 2>&1 || { fail "coderabbit not on PATH"; return 1; }
  if ! coderabbit usage >/dev/null 2>&1; then
    fail "CodeRabbit not authenticated — run: coderabbit auth login"
    return 1
  fi
  git -C "$REPO_DIR" rev-parse --verify --quiet "$branch" >/dev/null 2>&1 || {
    fail "no local branch $branch"; return 1; }

  # Review what the PR ACTUALLY HAS, not what happens to be in the local branch.
  # The status is written against GitHub's headRefOid; reviewing an unpushed
  # local commit would publish a verdict about code the PR does not contain.
  git -C "$REPO_DIR" fetch -q origin "$branch" 2>/dev/null
  local ref="origin/$branch"
  git -C "$REPO_DIR" rev-parse --verify --quiet "$ref" >/dev/null 2>&1 || ref="$branch"
  local sha; sha="$(git -C "$REPO_DIR" rev-parse "$ref" 2>/dev/null)"
  local local_sha; local_sha="$(git -C "$REPO_DIR" rev-parse "$branch" 2>/dev/null)"
  if [ "$ref" != "$branch" ] && [ "$sha" != "$local_sha" ]; then
    say "  note: reviewing $ref ($(printf '%s' "$sha" | cut -c1-7)); the local branch is at $(printf '%s' "$local_sha" | cut -c1-7)"
    say "        push the branch first if you meant to review the local commits"
  fi

  local wt; wt="${TMPDIR:-/tmp}/fh-regate.$issue.$$"
  rm -rf "$wt"
  git -C "$REPO_DIR" worktree add --detach "$wt" "$sha" >/dev/null 2>&1 || {
    fail "could not create a review worktree for $ref"; return 1; }
  # Always reap the worktree, including on Ctrl-C — a leaked one keeps a stale
  # entry in .git/worktrees and confuses later `git worktree add`.
  trap 'rm -rf "$wt"; git -C "$REPO_DIR" worktree prune >/dev/null 2>&1' RETURN INT TERM

  local out; out="$(next_round_file "$issue" "$LOG_DIR")"
  mkdir -p "$LOG_DIR"
  say "Reviewing $ref @ $(printf '%s' "$sha" | cut -c1-7) against $BASE_BRANCH — round $(round_number "$out")"
  say "  (a full-branch review; the builder's rounds compared against the branch below)"
  ( cd "$wt" && coderabbit review --committed --base "$BASE_BRANCH" ) > "$out" 2>&1
  local rc=$?
  # Record WHAT was reviewed next to the log, so publishing can prove the verdict
  # belongs to the commit the PR is actually at.
  printf '%s\n' "$sha" > "${out%.txt}.sha"

  if round_unavailable "$out"; then
    fail "CodeRabbit did not review the branch — see $out"
    return 1
  fi
  if [ "$rc" -ne 0 ]; then
    fail "coderabbit review exited $rc — the round is not a review, see $out"
    return 1
  fi
  say "  round complete (rc=$rc): $(round_blocking_count "$out") blocking finding(s) → $out"
  return 0
}

# A clean gate is the whole reason the PR was opened as a draft, so clearing the
# draft is the other half of publishing the verdict — otherwise every PR the
# builder opens stays a draft forever and the stack never becomes reviewable.
# Only ever called when VERDICT_STATE is success.
promote_pr() {
  local pr_number="$1" is_draft="$2"
  if [ "$is_draft" != "true" ]; then
    say "  PR #$pr_number is already ready for review"
    return 0
  fi
  if gh pr ready "$pr_number" >/dev/null 2>&1; then
    say "  PR #$pr_number marked ready for review (gate is clean)"
  else
    fail "  could not mark PR #$pr_number ready — do it by hand: gh pr ready $pr_number"
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

usage() {
  cat >&2 <<'EOF'
usage: pr_gate.sh ISSUE            publish the findings trail + status for ISSUE's PR
       pr_gate.sh --regate ISSUE   re-review the whole branch vs development, then publish
       pr_gate.sh --stack          publish every open stacked PR, bottom-up
       pr_gate.sh --require-check  make coderabbit/cli-gate required on development

  --no-promote   leave a clean PR as a draft (default: mark it ready for review)
EOF
  exit 2
}

# Publish one issue's trail: comment, commit status, and — when the gate is
# clean — clear the draft. Returns the verdict, so a caller walking a stack can
# stop at the first PR that is not mergeable.
publish_for_issue() {
  local issue="$1"
  local branch; branch="$(issue_branch "$issue")"
  local pr_json
  if ! pr_json="$(gh pr view "$branch" --json number,headRefOid,url,isDraft 2>&1)"; then
    fail "no PR found for branch $branch — $pr_json"
    return 1
  fi
  local pr_number pr_sha pr_url pr_draft
  eval "$(printf '%s' "$pr_json" | python3 -c '
import json, shlex, sys
d = json.load(sys.stdin)
for k, v in (("pr_number", d["number"]), ("pr_sha", d["headRefOid"]),
             ("pr_url", d["url"]), ("pr_draft", str(d["isDraft"]).lower())):
    print(f"{k}={shlex.quote(str(v))}")' 2>/dev/null)"
  [ -n "${pr_number:-}" ] && [ -n "${pr_sha:-}" ] || { fail "could not parse PR info for $branch"; return 1; }

  local repo_slug; repo_slug="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"
  [ -n "$repo_slug" ] || { fail "could not resolve repo slug"; return 1; }

  local report; report="$(build_report "$issue" "$LOG_DIR" "$REPO_DIR")"
  gate_verdict "$issue" "$LOG_DIR"

  # A clean verdict is about a specific tree. If the final round recorded which
  # commit it reviewed and the PR has since moved, that verdict describes code
  # that is no longer there — publishing success would green an unreviewed head.
  # No recorded sha means "cannot verify" (builder rounds predate the PR), which
  # is left as-is rather than upgraded to proof.
  if [ "$VERDICT_STATE" = "success" ]; then
    local last_round reviewed
    last_round="$(round_files "$issue" "$LOG_DIR" | tail -1)"
    reviewed="$(round_sha "$last_round")"
    if [ -n "$reviewed" ] && [ "$reviewed" != "$pr_sha" ]; then
      VERDICT_STATE="failure"
      VERDICT_DESC="reviewed $(printf '%s' "$reviewed" | cut -c1-7), PR head is $(printf '%s' "$pr_sha" | cut -c1-7) — re-gate"
    fi
  fi

  publish_comment "$repo_slug" "$pr_number" "$issue" "$report"

  local gh_state; gh_state="failure"; [ "$VERDICT_STATE" = "success" ] && gh_state="success"
  gh api "repos/$repo_slug/statuses/$pr_sha" \
    -f state="$gh_state" \
    -f context="$GATE_CONTEXT" \
    -f description="$(printf '%s' "$VERDICT_DESC" | cut -c1-140)" \
    -f target_url="${LAST_COMMENT_URL:-$pr_url}" \
    >/dev/null

  say "PR #$pr_number ($issue): $GATE_CONTEXT = $gh_state — $VERDICT_DESC"
  if [ "$VERDICT_STATE" = "success" ] && [ "$PROMOTE" = "1" ]; then
    promote_pr "$pr_number" "${pr_draft:-false}"
  fi
  [ "$VERDICT_STATE" = "success" ]
}

# Walk every open PR from BASE_BRANCH upward. Stops at the first PR whose gate is
# not clean: a stack is merged bottom-up, so a blocked PR blocks everything above
# it and publishing the rest would only be noise.
publish_stack() {
  local rows; rows="$(gh pr list --state open --limit 100 \
      --json number,baseRefName,headRefName \
      -q '.[] | "\(.number)\t\(.baseRefName)\t\(.headRefName)"' 2>/dev/null)"
  [ -n "$rows" ] || { say "No open PRs."; return 0; }

  local order; order="$(pr_stack_order "$BASE_BRANCH" "$rows")"
  [ -n "$order" ] || { fail "no PR in the stack bases on $BASE_BRANCH"; return 1; }

  local n head issue rc=0
  say "Stack (bottom-up): $(printf '%s' "$order" | tr '\n' ' ')"
  for n in $order; do
    head="$(printf '%s\n' "$rows" | awk -F'\t' -v n="$n" '$1 == n { print $3; exit }')"
    issue="$(printf '%s' "${head#feature/}" | tr '[:lower:]' '[:upper:]')"
    say "── PR #$n · $issue"
    if ! publish_for_issue "$issue"; then
      rc=1
      say "   stopping — everything above #$n waits on this one"
      break
    fi
  done
  return $rc
}

main() {
  # shellcheck disable=SC1091
  [ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

  for t in git gh python3; do
    command -v "$t" >/dev/null 2>&1 || { fail "$t not found on PATH"; exit 1; }
  done

  local mode="publish" issue=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --require-check) mode="require-check" ;;
      --regate)        mode="regate"; issue="${2:-}"; [ $# -gt 1 ] && shift ;;
      --stack)         mode="stack" ;;
      --no-promote)    PROMOTE=0 ;;
      --*)             usage ;;
      *)               issue="$1" ;;
    esac
    shift
  done

  [ "$mode" = "require-check" ] && { require_check; exit $?; }
  gh auth status >/dev/null 2>&1 || { fail "gh not authenticated — run: gh auth login"; exit 1; }

  case "$mode" in
    stack)  publish_stack; exit $? ;;
    regate) [ -n "$issue" ] || usage
            regate "$issue" || exit 1
            publish_for_issue "$issue"; exit $? ;;
    *)      [ -n "$issue" ] || usage
            publish_for_issue "$issue"; exit $? ;;
  esac
}

# Sourced by ops/pr_gate.test.sh to unit-test the pure helpers above without
# touching gh or the network; only run main() when executed directly.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi

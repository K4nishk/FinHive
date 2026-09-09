#!/usr/bin/env bash
# ops/orchestrator.sh — the build loop.  [KCH-76]
#
# Walks ops/queue.tsv in build order and, for each unbuilt issue:
#   1. branch feature/<issue> from the top of the stack
#   2. run the implementing agent against the Linear issue body
#   3. run the CodeRabbit CLI gate PRE-PUSH
#   4. return blocking findings to the agent, at most CR_MAX_ROUNDS times
#   5. if findings survive, mediate: fix / dismiss with rationale / escalate to Linear
#   6. push and open a stacked PR
#
# NOTHING MERGES WITHOUT A HUMAN. This script opens PRs; it never merges one.
#
# One-shot by design: it walks the queue and exits. ops/run_builder.sh is what makes
# it repeatable, and decides whether a pass is warranted at all.
#
# Rules carried from AssetAuditor/ops — each cost a real session:
#   1. Re-exec from $TMPDIR. This script rewrites the worktree it lives in; a
#      `git reset --hard` mid-run would swap the file out from under bash, which
#      reads scripts lazily and would then execute a mixture of two versions.
#      State stays in the repo via FH_REAL_OPS.
#   2. Take ops/.worktree.lock around every checkout. The tmux panes, the sweeper
#      and this loop share one checkout.
#   3. Pick the stack tip by COMMITS AHEAD of development, never by commit date.
#      A late fix commit pushed to an early branch makes the bottom of the stack
#      look like the newest branch, and everything stacks onto a stub.
#   4. A merged PR deletes its branch, so a base computed minutes ago can vanish.
#      Retarget to development rather than failing.

set -uo pipefail

# ── relocate (rule 1) ────────────────────────────────────────────────────────
if [ "${FH_RELOCATED:-}" != "1" ]; then
  _src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  _copy="${TMPDIR:-/tmp}/finhive-orchestrator.$$.sh"
  cp "$_src/orchestrator.sh" "$_copy" || exit 1
  chmod +x "$_copy"
  FH_RELOCATED=1 FH_REAL_OPS="$_src" exec "$_copy" "$@"
fi

OPS_DIR="${FH_REAL_OPS:?FH_REAL_OPS unset — relocation failed}"
REPO_DIR="$(cd "$OPS_DIR/.." && pwd)"
LOG_DIR="$OPS_DIR/logs"
QUEUE="$OPS_DIR/queue.tsv"
DONE="$OPS_DIR/.completed_issues"
WT_LOCK="$OPS_DIR/.worktree.lock"
ESCALATIONS="$OPS_DIR/.escalations.tsv"
mkdir -p "$LOG_DIR"
cd "$REPO_DIR" || exit 1

# shellcheck disable=SC1091
[ -f "$OPS_DIR/.env.local" ] && . "$OPS_DIR/.env.local"

BASE_BRANCH="${BASE_BRANCH:-development}"
IMPL_MODEL="${IMPL_MODEL:-claude-sonnet-5}"
MEDIATOR_MODEL="${MEDIATOR_MODEL:-claude-opus-5}"
MAX_TURNS="${MAX_TURNS:-60}"
CR_MAX_ROUNDS="${CR_MAX_ROUNDS:-2}"
CR_BLOCKING="${CR_BLOCKING:-critical|major|blocker|high}"
PERM_MODE="${PERM_MODE:-acceptEdits}"
MAX_ISSUES="${MAX_ISSUES:-0}"          # 0 = drain the queue

say()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }

# ── preflight ────────────────────────────────────────────────────────────────
for t in git gh claude coderabbit python3; do
  command -v "$t" >/dev/null 2>&1 || { fail "$t not found on PATH"; exit 1; }
done
[ -f "$QUEUE" ] || { fail "no queue at $QUEUE — run: python3 ops/seed_linear.py --write-queue"; exit 1; }
[ -n "${LINEAR_API_KEY:-}" ] || { fail "LINEAR_API_KEY unset (ops/.env.local)"; exit 1; }
gh auth status >/dev/null 2>&1 || { fail "gh not authenticated — run: gh auth login"; exit 1; }

# ── helpers ──────────────────────────────────────────────────────────────────

pending_issues() {
  comm -23 \
    <(grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$QUEUE" | cut -f2 | sort) \
    <(sort "$DONE" 2>/dev/null || true)
}

# Queue order, filtered to what is still pending. comm needs sorted input, so the
# ordering has to be restored from the file afterwards.
next_issues() {
  local pend; pend="$(pending_issues)"
  [ -z "$pend" ] && return 0
  grep -vE '^[[:space:]]*#|^[[:space:]]*$' "$QUEUE" | cut -f2 \
    | grep -Fx -f <(printf '%s\n' "$pend")
}

issue_title() { grep -P "^\d+\t$1\t" "$QUEUE" 2>/dev/null | cut -f5 | head -1; }

# Rule 3: deepest unmerged feature branch, measured in commits ahead of the base.
stack_tip() {
  local best="" bestn=0 n
  for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/feature/ 2>/dev/null); do
    git merge-base --is-ancestor "$b" "origin/$BASE_BRANCH" 2>/dev/null && continue
    n="$(git rev-list --count "origin/$BASE_BRANCH..$b" 2>/dev/null || echo 0)"
    if [ "$n" -gt "$bestn" ]; then bestn="$n"; best="${b#origin/}"; fi
  done
  printf '%s' "$best"
}

take_lock() {
  local waited=0
  until mkdir "$WT_LOCK" 2>/dev/null; do
    [ "$waited" -ge 300 ] && { fail "worktree lock held >5min — another agent is running"; return 1; }
    sleep 5; waited=$((waited + 5))
  done
  return 0
}
drop_lock() { rm -rf "$WT_LOCK" 2>/dev/null || true; }

# Fetch the issue body from Linear so the agent implements the spec, not a guess.
fetch_issue() {
  python3 - "$1" <<'PY'
import json, os, sys, urllib.request
ident = sys.argv[1]
q = 'query($id:String!){issue(id:$id){identifier title description estimate project{name}}}'
r = urllib.request.Request("https://api.linear.app/graphql",
    data=json.dumps({"query": q, "variables": {"id": ident}}).encode(),
    headers={"Content-Type": "application/json", "Authorization": os.environ["LINEAR_API_KEY"]})
try:
    i = json.load(urllib.request.urlopen(r, timeout=45))["data"]["issue"]
except Exception as exc:                       # noqa: BLE001 - surfaced to the caller
    print(f"__FETCH_FAILED__ {exc}", file=sys.stderr); sys.exit(1)
if not i:
    print("__FETCH_FAILED__ no such issue", file=sys.stderr); sys.exit(1)
print(f"{i['identifier']} · {i['title']}\nProject: {(i['project'] or {}).get('name','-')}\n\n{i['description'] or ''}")
PY
}

# Open a Linear issue recording why an agent could not clear a finding (rule: after
# CR_MAX_ROUNDS the loop escalates with context rather than burning more rounds).
escalate() {
  local parent="$1" findings="$2" attempts="$3"
  python3 - "$parent" "$findings" "$attempts" <<'PY'
import json, os, sys, urllib.request
parent, findings, attempts = sys.argv[1], sys.argv[2], sys.argv[3]
def gql(q, v):
    r = urllib.request.Request("https://api.linear.app/graphql",
        data=json.dumps({"query": q, "variables": v}).encode(),
        headers={"Content-Type": "application/json", "Authorization": os.environ["LINEAR_API_KEY"]})
    return json.load(urllib.request.urlopen(r, timeout=45))["data"]
src = gql('query($id:String!){issue(id:$id){title team{id} project{id}}}', {"id": parent})["issue"]
body = (f"## Escalated from {parent}\n\n"
        f"Blocking findings survived {attempts} fix cycle(s).\n\n"
        f"### Findings still open\n```\n{findings[:4000]}\n```\n\n"
        f"### Why this needs a human\n"
        f"The loop stops after two cycles by design: cycle 1 catches mechanical issues, "
        f"cycle 2 catches a wrong first fix. A third almost always means a design "
        f"constraint the agent cannot see, and more rounds are waste.\n")
res = gql('mutation($i:IssueCreateInput!){issueCreate(input:$i){success issue{identifier url}}}',
          {"i": {"teamId": src["team"]["id"],
                 "projectId": (src["project"] or {}).get("id"),
                 "title": f"[escalated] {src['title'][:180]}",
                 "description": body, "priority": 1}})["issueCreate"]
print(res["issue"]["identifier"] if res["success"] else "ESCALATION_FAILED")
PY
}

# ── the gate ─────────────────────────────────────────────────────────────────
# Runs pre-push so fix commits land in the PR's first commit set. Returns 0 when the
# final round is clean, 1 when blocking findings survive.
run_gate() {
  local issue="$1" prompt_file="$2" round=0 out
  while :; do
    out="$LOG_DIR/${issue}_cr_round${round}.txt"
    say "  CodeRabbit gate, round $round"
    if ! coderabbit review --plain > "$out" 2>&1; then
      # A gate that cannot run is not a pass. Say so and let the human look.
      if grep -qiE 'rate.?limit|quota|too many requests' "$out"; then
        say "  gate unavailable (quota) — banking as review debt, not treating as clean"
        printf '%s\t%s\tquota\n' "$issue" "$(date -u +%FT%TZ)" >> "$OPS_DIR/.review_debt.tsv"
        return 2
      fi
      say "  gate errored — see $out"
      return 2
    fi
    local blocking
    blocking="$(grep -icE "$CR_BLOCKING" "$out" || true)"
    if [ "${blocking:-0}" -eq 0 ]; then
      say "  gate clean at round $round"
      return 0
    fi
    say "  $blocking blocking finding(s) at round $round"
    if [ "$round" -ge "$CR_MAX_ROUNDS" ]; then
      return 1
    fi
    round=$((round + 1))
    say "  returning findings to the agent (cycle $round of $CR_MAX_ROUNDS)"
    {
      echo "The CodeRabbit CLI gate returned blocking findings on your change."
      echo "Fix them. Do not disable the check, weaken an assertion, or delete a test."
      echo
      cat "$out"
    } > "$prompt_file"
    claude -p --model "$IMPL_MODEL" --max-turns "$MAX_TURNS" \
           --permission-mode "$PERM_MODE" "$(cat "$prompt_file")" \
           >> "$LOG_DIR/${issue}_agent.log" 2>&1
    git add -A && git commit -q -m "fix($issue): address CodeRabbit round $round" 2>/dev/null || true
  done
}

# ── one issue, end to end ────────────────────────────────────────────────────
run_issue() {
  local issue="$1"
  local branch="feature/$(echo "$issue" | tr '[:upper:]' '[:lower:]')"
  local title; title="$(issue_title "$issue")"

  say "── $issue · ${title:-untitled}"

  take_lock || return 1
  # shellcheck disable=SC2064
  trap "drop_lock" RETURN

  git fetch --prune origin --quiet 2>/dev/null || { fail "git fetch failed"; return 1; }
  git reset --hard --quiet HEAD 2>/dev/null || true
  git clean -fdq 2>/dev/null || true      # locks are gitignored (rule 2); this is safe

  local base; base="$(stack_tip)"
  if [ -n "$base" ] && git rev-parse --verify --quiet "origin/$base" >/dev/null; then
    say "  stacking on $base ($(git rev-list --count "origin/$BASE_BRANCH..origin/$base") ahead)"
  else
    base="$BASE_BRANCH"; say "  branching from $BASE_BRANCH"
  fi

  git checkout -q -B "$branch" "origin/$base" 2>/dev/null || {
    fail "could not create $branch from origin/$base"; return 1; }

  local spec; spec="$(fetch_issue "$issue")" || { fail "could not read $issue from Linear"; return 1; }
  local before; before="$(git rev-parse HEAD)"

  say "  implementing with $IMPL_MODEL"
  claude -p --model "$IMPL_MODEL" --max-turns "$MAX_TURNS" --permission-mode "$PERM_MODE" \
    "$(printf '%s\n\n%s\n' \
       "Implement this Linear issue in the FinHive repository. Follow CLAUDE.md. Make the smallest correct change, add tests, and commit. Do not merge anything, do not push, and do not modify files under ops/ unless the issue says to." \
       "$spec")" \
    > "$LOG_DIR/${issue}_agent.log" 2>&1
  local rc=$?

  git add -A 2>/dev/null || true
  git commit -q -m "$issue: ${title:-implement}" 2>/dev/null || true

  if [ "$(git rev-parse HEAD)" = "$before" ]; then
    fail "$issue produced no commits (agent rc=$rc) — see $LOG_DIR/${issue}_agent.log"
    return 1
  fi

  run_gate "$issue" "$LOG_DIR/${issue}_gate_prompt.txt"
  local gate=$?
  if [ "$gate" -eq 1 ]; then
    say "  findings survived $CR_MAX_ROUNDS cycles — mediating with $MEDIATOR_MODEL"
    local last; last="$(ls -1t "$LOG_DIR/${issue}"_cr_round*.txt 2>/dev/null | head -1)"
    local esc; esc="$(escalate "$issue" "$(cat "$last" 2>/dev/null)" "$CR_MAX_ROUNDS")"
    printf '%s\t%s\t%s\n' "$issue" "$esc" "$(date -u +%FT%TZ)" >> "$ESCALATIONS"
    say "  escalated to $esc — PR will open as draft"
  fi

  git push -q --force-with-lease -u origin "$branch" 2>/dev/null || {
    fail "push failed for $branch"; return 1; }

  # Rule 4: the base can be merged and deleted while we work.
  local pr_base="$base"
  if [ "$base" != "$BASE_BRANCH" ] && ! git rev-parse --verify --quiet "origin/$base" >/dev/null; then
    say "  base $base vanished (merged) — retargeting to $BASE_BRANCH"
    pr_base="$BASE_BRANCH"
  fi

  local body pr
  body="$(printf '%s\n\n%s\n\n%s\n' \
    "Implements **$issue** — ${title:-}" \
    "CodeRabbit CLI gate: $([ "$gate" -eq 0 ] && echo 'clean' || [ "$gate" -eq 2 ] && echo 'unavailable — review by hand' || echo "findings escalated after $CR_MAX_ROUNDS cycles")" \
    "Stacked on \`$pr_base\`. Review and merge **bottom-up**.")"

  if pr="$(gh pr create --base "$pr_base" --head "$branch" \
            --title "$issue: ${title:-implement}" --body "$body" \
            $([ "$gate" -ne 0 ] && echo --draft) 2>&1)"; then
    say "  PR: $pr"
  else
    fail "gh pr create failed — the push succeeded, so nothing is lost. Open it by hand:"
    fail "  gh pr create --base $pr_base --head $branch --title \"$issue\""
    fail "  $pr"
    return 1
  fi

  # Only a fully successful run is recorded, so a failure retries on the next pass.
  [ "$gate" -eq 0 ] && echo "$issue" >> "$DONE"
  return 0
}

# ── main ─────────────────────────────────────────────────────────────────────
mapfile -t QUEUED < <(next_issues)
if [ "${#QUEUED[@]}" -eq 0 ]; then
  say "Queue exhausted — nothing to build."; exit 0
fi

say "Queue: ${#QUEUED[@]} issue(s) pending. Base=$BASE_BRANCH impl=$IMPL_MODEL rounds=$CR_MAX_ROUNDS"
built=0
for issue in "${QUEUED[@]}"; do
  if run_issue "$issue"; then built=$((built + 1)); else say "  $issue did not complete — will retry next pass"; fi
  [ "$MAX_ISSUES" -gt 0 ] && [ "$built" -ge "$MAX_ISSUES" ] && { say "MAX_ISSUES=$MAX_ISSUES reached."; break; }
done
say "Pass complete — $built issue(s) built, $(pending_issues | grep -c . || echo 0) still pending."

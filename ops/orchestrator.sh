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
  _dir="${TMPDIR:-/tmp}/finhive-ops.$$"
  mkdir -p "$_dir" || exit 1
  # Relocate the HELPERS too, not just this script. run_issue resets the worktree,
  # which can delete a helper that only exists in an unpushed commit — the loop then
  # calls a script that is no longer there and misreads the failure. Relocating
  # orchestrator.sh alone left usage.py exposed to exactly that.
  cp "$_src/orchestrator.sh" "$_dir/" || exit 1
  for _h in usage.py pr_gate.sh; do
    [ -f "$_src/$_h" ] && cp "$_src/$_h" "$_dir/"
  done
  chmod +x "$_dir"/*.sh "$_dir"/*.py 2>/dev/null
  FH_RELOCATED=1 FH_REAL_OPS="$_src" FH_TMP_OPS="$_dir" exec "$_dir/orchestrator.sh" "$@"
fi

OPS_DIR="${FH_REAL_OPS:?FH_REAL_OPS unset — relocation failed}"
REPO_DIR="$(cd "$OPS_DIR/.." && pwd)"
LOG_DIR="$OPS_DIR/logs"
QUEUE="$OPS_DIR/queue.tsv"
DONE="$OPS_DIR/.completed_issues"
WT_LOCK="$OPS_DIR/.worktree.lock"
ESCALATIONS="$OPS_DIR/.escalations.tsv"
STUCK="$OPS_DIR/.stuck_issues.tsv"
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
MAX_ISSUES="${MAX_ISSUES:-0}"          # 0 = drain the queue (or until the budget)
STUCK_MAX="${STUCK_MAX:-2}"            # consecutive no-commit failures before an issue is parked

# Budget. There is no API for the remaining balance of a 5-hour window, so this
# meters what THIS LOOP spends, not the window itself — anything you spend in an
# interactive session counts against the same window and is invisible here. The
# reliable signal is a usage-limit response from the CLI, which is a hard stop
# regardless of this number.
SESSION_BUDGET_USD="${SESSION_BUDGET_USD:-20}"
BUDGET_THRESHOLD_PCT="${BUDGET_THRESHOLD_PCT:-95}"
KILL_TMUX_ON_WINDDOWN="${KILL_TMUX_ON_WINDDOWN:-1}"
TMUX_SESSION="${FINHIVE_TMUX_SESSION:-finhive}"
export SESSION_BUDGET_USD BUDGET_THRESHOLD_PCT

# One id per pass, so the ledger and the summary group correctly.
FH_SESSION_ID="${FH_SESSION_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export FH_SESSION_ID
SESSION_START="$(date +%s)"
# Run the relocated copy — the in-repo one can vanish when the worktree resets.
USAGE="${FH_TMP_OPS:-$OPS_DIR}/usage.py"
[ -f "$USAGE" ] || USAGE="$OPS_DIR/usage.py"

say()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }

# ── preflight ────────────────────────────────────────────────────────────────
# macOS ships bash 3.2 (2007). Everything below is written to run on it — no
# mapfile, no associative arrays, no ${x,,}. This check exists so that if someone
# later adds a bash-4 construct, the failure names the cause instead of surfacing
# as "command not found" three hundred lines in.
if [ "${BASH_VERSINFO[0]:-0}" -lt 3 ]; then
  fail "bash 3.2 or newer required (found ${BASH_VERSION:-unknown})"; exit 1
fi

for t in git gh claude coderabbit python3; do
  command -v "$t" >/dev/null 2>&1 || { fail "$t not found on PATH"; exit 1; }
done
[ -f "$QUEUE" ] || { fail "no queue at $QUEUE — run: python3 ops/seed_linear.py --write-queue"; exit 1; }
[ -n "${LINEAR_API_KEY:-}" ] || { fail "LINEAR_API_KEY unset (ops/.env.local)"; exit 1; }
gh auth status >/dev/null 2>&1 || { fail "gh not authenticated — run: gh auth login"; exit 1; }

# Check the review gate BEFORE building anything. An unauthenticated CodeRabbit
# fails once per issue, mid-run, after the agent has already spent its tokens —
# and every PR opens as an unreviewed draft. Fail here instead.
if ! coderabbit usage >/dev/null 2>&1; then
  fail "CodeRabbit not authenticated — run: coderabbit auth login"
  fail "The review gate is the point of this loop; refusing to build without it."
  fail "Set SKIP_GATE=1 to build anyway (every PR opens as an unreviewed draft)."
  [ "${SKIP_GATE:-0}" = "1" ] || exit 1
fi

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

# BSD grep (macOS) has no -P, so the original PCRE pattern matched nothing and every
# issue logged as "untitled". awk is portable and reads the field directly.
issue_title() { awk -F'\t' -v i="$1" '$2 == i { print $5; exit }' "$QUEUE" 2>/dev/null; }

# Rule 3: deepest unmerged feature branch, measured in commits ahead of the base.
# $1 = the branch being built, excluded so an issue never stacks on itself.
# Rebuilding KCH-78 picked feature/kch-78 as its own base, which reset the branch
# onto its own tip — the agent then saw the work already done and made no commits.
stack_tip() {
  local skip="${1:-}" best="" bestn=0 n short
  for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/feature/ 2>/dev/null); do
    short="${b#origin/}"
    [ -n "$skip" ] && [ "$short" = "$skip" ] && continue
    git merge-base --is-ancestor "$b" "origin/$BASE_BRANCH" 2>/dev/null && continue
    n="$(git rev-list --count "origin/$BASE_BRANCH..$b" 2>/dev/null || echo 0)"
    if [ "$n" -gt "$bestn" ]; then bestn="$n"; best="$short"; fi
  done
  printf '%s' "$best"
}

# ── metered agent invocation ─────────────────────────────────────────────────
# Every claude call goes through here so nothing spends untracked. Writes the
# JSON result, records it, and echoes the classification so callers can branch.
# Sets AGENT_KIND to ok|limit|auth|error.
run_agent() {
  local issue="$1" phase="$2" model="$3" prompt="$4"
  local jf="$LOG_DIR/${issue}_${phase}_$(date +%s).json"
  # Published so the caller can read THIS call's answer. The _agent.log is
  # appended across passes, so grepping it would match a previous run's verdict.
  AGENT_JSON="$jf"

  claude -p --output-format json --model "$model" --max-turns "$MAX_TURNS" \
         --permission-mode "$PERM_MODE" "$prompt" > "$jf" 2>>"$LOG_DIR/${issue}_agent.log"

  local line; line="$(python3 "$USAGE" record "$jf" --issue "$issue" --phase "$phase" --model "$model" 2>/dev/null)"
  AGENT_KIND="$(printf '%s' "$line" | sed -n 's/.*kind=\([a-z]*\).*/\1/p')"
  [ -n "$AGENT_KIND" ] || AGENT_KIND="ok"

  # Keep the human-readable answer next to the JSON; the log is what a person reads.
  python3 -c "
import json,sys
try: print(json.load(open(sys.argv[1])).get('result',''))
except Exception: pass" "$jf" >> "$LOG_DIR/${issue}_agent.log" 2>/dev/null

  say "    agent[$phase] $line"
  [ "$AGENT_KIND" = "ok" ]
}

# Consecutive no-commit failures per issue. An issue the agent cannot move is a
# human's problem; without this it is re-attempted on every pass at full token
# cost and blocks nothing but the budget.
stuck_count() { awk -F'\t' -v i="$1" '$1 == i { n = $2 } END { print n + 0 }' "$STUCK" 2>/dev/null || echo 0; }
stuck_clear() { [ -f "$STUCK" ] && grep -v "^$1	" "$STUCK" > "$STUCK.tmp" 2>/dev/null && mv "$STUCK.tmp" "$STUCK"; return 0; }
stuck_bump() {
  local n; n="$(stuck_count "$1")"
  stuck_clear "$1"
  printf '%s\t%s\t%s\n' "$1" "$((n + 1))" "$(date -u +%FT%TZ)" >> "$STUCK"
}

# The VERDICT= line from the last agent call, or empty. Reads the JSON of THIS
# call, never the appended log, so a previous pass's verdict cannot leak in.
agent_verdict() {
  [ -n "${AGENT_JSON:-}" ] && [ -f "$AGENT_JSON" ] || return 0
  python3 -c "
import json,re,sys
try: txt = json.load(open(sys.argv[1])).get('result','') or ''
except Exception: sys.exit(0)
m = re.findall(r'^\s*VERDICT=([A-Z_]+)', txt, re.M)
print(m[-1] if m else '')" "$AGENT_JSON" 2>/dev/null
}

# 0 = room left · 1 = at/over threshold · 2 = platform said stop
#
# Trusts the VERDICT sentinel, not the exit code. python exits 2 on an argparse
# error and on a missing file, which previously read as "platform hard stop" and
# wound the loop down for no reason. A broken meter is a warning, not a stop.
budget_state() {
  local out verdict
  out="$(python3 "$USAGE" check --budget-usd "$SESSION_BUDGET_USD" \
         --threshold "$BUDGET_THRESHOLD_PCT" 2>&1)"
  verdict="$(printf '%s\n' "$out" | sed -n 's/^VERDICT=\(.*\)$/\1/p' | tail -1)"
  printf '%s\n' "$out" | grep -v '^VERDICT=' || true
  case "$verdict" in
    OK)        return 0 ;;
    THRESHOLD) return 1 ;;
    HARDSTOP)  return 2 ;;
    *)
      say "  WARNING: usage meter did not report (is ops/usage.py present?) — continuing unmetered"
      return 0 ;;
  esac
}

# ── wind-down ────────────────────────────────────────────────────────────────
# Called when the budget threshold is reached or the platform hard-stops us.
# The remaining tokens are NOT spent on more building — they go to making the
# in-flight work recoverable, because a half-finished branch that was never
# pushed is the one thing this loop can actually lose.
wind_down() {
  local reason="$1"
  say ""
  say "══ WIND-DOWN · $reason"

  # 1. Back up in-flight work. Commit whatever is uncommitted and push the
  #    branch so nothing lives only on this machine.
  local br; br="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    say "  uncommitted work on $br — committing as WIP"
    git add -A 2>/dev/null || true
    git commit -q -m "WIP: wind-down backup ($reason)" 2>/dev/null || true
  fi
  case "$br" in
    feature/*)
      if git push -q --force-with-lease -u origin "$br" 2>/dev/null; then
        say "  pushed $br"
      else
        say "  WARNING: could not push $br — the work is committed locally only"
      fi ;;
    *) say "  on $br — nothing to push" ;;
  esac

  # 2. Session summary, to stdout and to a file the tmux pane leaves behind.
  local summary="$LOG_DIR/SESSION_${FH_SESSION_ID}.md"
  {
    echo "# Build session $FH_SESSION_ID"
    echo
    echo "- ended: $reason"
    echo "- duration: $(( ($(date +%s) - SESSION_START) / 60 )) min"
    echo "- issues completed: $(comm -12 <(sort "$DONE" 2>/dev/null) <(printf '%s\n' "$SESSION_BUILT" | tr ' ' '\n' | sort) 2>/dev/null | grep -c . || true)"
    echo "- built this session: ${SESSION_BUILT:-none}"
    echo "- still pending: $(pending_issues | grep -c . || true)"
    [ -n "$SESSION_STUCK" ] && echo "- parked (no commits after $STUCK_MAX tries):$SESSION_STUCK"
    [ -s "$ESCALATIONS" ] && { echo "- escalations:"; sed 's/^/  - /' "$ESCALATIONS"; }
    echo
    echo '```'
    python3 "$USAGE" report 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g'
    echo '```'
  } > "$summary"

  say ""
  python3 "$USAGE" report 2>/dev/null | while IFS= read -r l; do say "$l"; done
  say "  summary written to $summary"

  # 3. Kill the tmux session last — after the summary exists on disk, so
  #    killing the pane cannot destroy the only copy of it.
  if [ "$KILL_TMUX_ON_WINDDOWN" = "1" ] && command -v tmux >/dev/null 2>&1; then
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
      say "  killing tmux session '$TMUX_SESSION'"
      tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    fi
  fi
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
  local issue="$1" prompt_file="$2" gate_base="${3:-$BASE_BRANCH}" round=0 out
  if [ "${SKIP_GATE:-0}" = "1" ]; then
    say "  SKIP_GATE=1 — gate not run"; return 2
  fi
  while :; do
    out="$LOG_DIR/${issue}_cr_round${round}.txt"
    say "  CodeRabbit gate, round $round"
    # Plain text IS the default mode in coderabbit 0.7.5 — there is no --plain
    # flag, and passing one makes the CLI print usage and exit non-zero, which
    # looks exactly like a clean review to a naive check. --committed scopes the
    # review to what this branch actually added over its base.
    if ! coderabbit review --committed --base "$gate_base" > "$out" 2>&1; then
      # A gate that cannot run is not a pass. Say so and let the human look.
      if grep -qiE 'not logged in|auth login|unauthor' "$out"; then
        say "  gate unavailable (not authenticated) — run: coderabbit auth login"
        return 2
      fi
      if grep -qiE 'unknown option|unknown command|Usage: coderabbit' "$out"; then
        say "  gate INVOCATION is wrong — the CLI rejected the command, see $out"
        return 2
      fi
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
    if ! run_agent "$issue" "gate" "$IMPL_MODEL" "$(cat "$prompt_file")"; then
      [ "$AGENT_KIND" = "limit" ] && { say "  usage limit during fix round"; return 3; }
    fi
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

  local base; base="$(stack_tip "$branch")"
  if [ -n "$base" ] && git rev-parse --verify --quiet "origin/$base" >/dev/null; then
    say "  stacking on $base ($(git rev-list --count "origin/$BASE_BRANCH..origin/$base") ahead)"
  else
    base="$BASE_BRANCH"; say "  branching from $BASE_BRANCH"
  fi

  # `checkout -B` RESETS an existing local branch to the start point, which silently
  # discards commits that were never pushed. That destroyed a commit on 2026-09-08,
  # including the helper the loop itself depends on. Refuse instead.
  if git rev-parse --verify --quiet "$branch" >/dev/null 2>&1; then
    local unpushed
    if git rev-parse --verify --quiet "origin/$branch" >/dev/null 2>&1; then
      unpushed="$(git rev-list --count "origin/$branch..$branch" 2>/dev/null || echo 0)"
    else
      unpushed="$(git rev-list --count "origin/$BASE_BRANCH..$branch" 2>/dev/null || echo 0)"
    fi
    if [ "${unpushed:-0}" -gt 0 ]; then
      fail "$branch has $unpushed unpushed commit(s) — refusing to reset and lose them"
      fail "  push them (git push -u origin $branch) or delete the branch, then re-run"
      return 1
    fi
  fi

  git checkout -q -B "$branch" "origin/$base" 2>/dev/null || {
    fail "could not create $branch from origin/$base"; return 1; }

  local spec; spec="$(fetch_issue "$issue")" || { fail "could not read $issue from Linear"; return 1; }
  local before; before="$(git rev-parse HEAD)"

  say "  implementing with $IMPL_MODEL"
  run_agent "$issue" "impl" "$IMPL_MODEL" \
    "$(printf '%s\n\n%s\n' \
       "Implement this Linear issue in the FinHive repository. Follow CLAUDE.md. Make the smallest correct change, add tests, and commit. Do not merge anything, do not push, and do not modify files under ops/ unless the issue says to.

End your final message with exactly one of these lines, on a line of its own:
VERDICT=IMPLEMENTED   — you committed the work
VERDICT=ALREADY_DONE  — the repository already satisfies this issue; name the commit that did it
VERDICT=BLOCKED       — you could not proceed; say why
The loop reads this line to decide whether to open a PR. Without it, work that is already finished is retried on every pass forever." \
       "$spec")"
  local rc=$?
  if [ "$AGENT_KIND" = "limit" ]; then
    say "  usage limit reached during implementation"
    return 3
  fi

  git add -A 2>/dev/null || true
  git commit -q -m "$issue: ${title:-implement}" >/dev/null 2>&1 || true

  # No commits is ambiguous: the agent may have failed, or the work may already
  # exist. Read as failure, KCH-78 sat at the head of the queue and was rebuilt
  # every pass — 144 issues behind it never started. The agent says which.
  if [ "$(git rev-parse HEAD)" = "$before" ]; then
    local verdict; verdict="$(agent_verdict)"
    if [ "$verdict" = "ALREADY_DONE" ]; then
      say "  $issue needs no change — the agent reports it already implemented"
      say "    (evidence in $LOG_DIR/${issue}_agent.log — verify before trusting it)"
      # The branch was created before the agent ran and carries no commits of its
      # own. Leaving it behind litters `git branch` with empty branches that look
      # like real work — and one of them pinned to a stack tip is exactly the
      # kind of thing someone later mistakes for an unpushed change.
      # $base may be a remote-only stack tip, so step off onto BASE_BRANCH, which
      # always exists locally. If that fails, keep the branch — a stray branch is
      # harmless, deleting one while it is checked out is not.
      if git checkout -q "$BASE_BRANCH" 2>/dev/null; then
        git branch -q -D "$branch" 2>/dev/null || true
      fi
      return 4
    fi
    fail "$issue produced no commits (agent rc=$rc, verdict=${verdict:-none}) — see $LOG_DIR/${issue}_agent.log"
    return 1
  fi

  run_gate "$issue" "$LOG_DIR/${issue}_gate_prompt.txt" "$base"
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
# No arrays here on purpose. macOS ships bash 3.2, which has no `mapfile`, and
# under `set -u` expanding an empty array is itself an error there. A plain file
# plus `while read` works on every bash and keeps the loop in the parent shell so
# the counter survives (a pipeline would put it in a subshell).
QUEUE_RUN="$LOG_DIR/.pending.$$"
next_issues > "$QUEUE_RUN"
trap 'rm -f "$QUEUE_RUN"' EXIT

TOTAL="$(grep -c . "$QUEUE_RUN" 2>/dev/null || echo 0)"
if [ "${TOTAL:-0}" -eq 0 ]; then
  say "Queue exhausted — nothing to build."; exit 0
fi

say "Queue: $TOTAL issue(s) pending. Base=$BASE_BRANCH impl=$IMPL_MODEL rounds=$CR_MAX_ROUNDS"
say "Budget: \$$SESSION_BUDGET_USD, wind down at ${BUDGET_THRESHOLD_PCT}%  (session $FH_SESSION_ID)"
built=0
SESSION_BUILT=""
SESSION_STUCK=""
ENDED=""

while IFS= read -r issue; do
  [ -n "$issue" ] || continue

  # Check BEFORE starting an issue, never mid-issue: stopping between issues
  # leaves a clean tree, stopping inside one leaves a half-built branch.
  budget_state; bstate=$?
  if [ "$bstate" -eq 2 ]; then ENDED="platform usage limit"; break; fi
  if [ "$bstate" -eq 1 ]; then ENDED="reached ${BUDGET_THRESHOLD_PCT}% of \$$SESSION_BUDGET_USD budget"; break; fi

  nstuck="$(stuck_count "$issue")"
  if [ "${nstuck:-0}" -ge "$STUCK_MAX" ]; then
    say "── $issue · SKIPPED — ${nstuck} failed attempts with no commits; needs a human"
    say "   unpark it with: grep -v '^$issue	' $STUCK > $STUCK.tmp && mv $STUCK.tmp $STUCK"
    SESSION_STUCK="$SESSION_STUCK $issue"
    continue
  fi

  run_issue "$issue"; irc=$?
  if [ "$irc" -eq 0 ]; then
    built=$((built + 1))
    SESSION_BUILT="$SESSION_BUILT $issue"
    stuck_clear "$issue"
  elif [ "$irc" -eq 4 ]; then
    # Already satisfied by work in the repo. Record it so the queue advances;
    # rebuilding it would produce nothing, forever.
    echo "$issue" >> "$DONE"
    SESSION_BUILT="$SESSION_BUILT $issue(already-done)"
    stuck_clear "$issue"
  elif [ "$irc" -eq 3 ]; then
    # The agent itself was cut off by the platform. Stop now — every further
    # call would fail the same way and burn the wind-down budget.
    SESSION_BUILT="$SESSION_BUILT $issue(partial)"
    ENDED="platform usage limit mid-issue"
    break
  else
    stuck_bump "$issue"
    if [ "$(stuck_count "$issue")" -ge "$STUCK_MAX" ]; then
      say "  $issue has now failed $STUCK_MAX times — skipping it from the next pass"
    else
      say "  $issue did not complete — will retry next pass"
    fi
  fi

  if [ "$MAX_ISSUES" -gt 0 ] && [ "$built" -ge "$MAX_ISSUES" ]; then
    ENDED="MAX_ISSUES=$MAX_ISSUES reached"; break
  fi
done < "$QUEUE_RUN"

[ -n "$ENDED" ] || ENDED="queue drained"
say ""
say "Pass complete — $built issue(s) built, $(pending_issues | grep -c . || true) still pending."
wind_down "$ENDED"

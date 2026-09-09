#!/usr/bin/env python3
"""Seed Linear from linear_import.csv.

Dry run by default. Nothing is created until --apply.

    export LINEAR_API_KEY=lin_api_...
    export LINEAR_TEAM_KEY=FIN            # the issue-id PREFIX, not the team name
    python3 ops/seed_linear.py            # dry run — prints the plan
    python3 ops/seed_linear.py --apply    # creates projects, labels, issues

Idempotent by issue title within the team: an existing title is skipped, so a
re-run after a partial failure resumes rather than duplicating.

CSV columns: Milestone, Workstream, Title, Description, Priority, Estimate, Labels, Status
  Milestone   becomes a Linear Project (created if missing) — M0..M5, in build order
  Workstream  added as a label alongside Labels (ops, ci-cd, backend, frontend, ...)
  Priority    1=Urgent 2=High 3=Medium 4=Low  (Linear's own scale)
  Estimate    must match the team's estimation scale (Fibonacci: 1,2,3,5,8,13)
  Labels      comma-separated inside the CSV cell; created if missing

Row order is build order. Issues are created top to bottom so Linear's issue numbers
run in the same sequence as the milestones — do not sort the CSV.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.linear.app/graphql"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "output" / "Loan Manager" / "mvp2" / "linear_import.csv"

DIM, RED, GRN, YEL, RST = "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[0m"


class LinearError(RuntimeError):
    pass


def gql(query: str, variables: dict | None = None, *, key: str, retries: int = 3) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": key},
        method="POST",
    )
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
            if "errors" in body:
                msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
                # Rate limits are worth waiting out; everything else is a real error.
                if "ratelimit" in msgs.lower() or "rate limit" in msgs.lower():
                    wait = 2 ** attempt
                    print(f"{YEL}  rate limited — waiting {wait}s{RST}", file=sys.stderr)
                    time.sleep(wait)
                    last = LinearError(msgs)
                    continue
                raise LinearError(msgs)
            return body["data"]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:400]
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"{YEL}  HTTP {exc.code} — retrying in {wait}s{RST}", file=sys.stderr)
                time.sleep(wait)
                last = LinearError(f"HTTP {exc.code}: {detail}")
                continue
            raise LinearError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise LinearError(f"network error: {exc}") from exc
        # A truncated chunked response raises IncompleteRead, and a dropped socket
        # raises a bare OSError — neither is a URLError, so without this branch the
        # retry loop is bypassed entirely and the traceback escapes to the user.
        except (http.client.IncompleteRead, http.client.HTTPException, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"{YEL}  truncated response ({type(exc).__name__}) — retrying in {wait}s{RST}",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            raise LinearError(f"connection failed after {retries} attempts: {exc}") from exc
    raise LinearError(f"exhausted retries: {last}")


# ── lookups ──────────────────────────────────────────────────────────────────

Q_TEAM = """
query($key: String!) {
  teams(filter: { key: { eq: $key } }) {
    nodes { id key name issueEstimationType }
  }
}
"""

Q_PROJECTS = """
query($teamId: String!) {
  team(id: $teamId) { projects(first: 250) { nodes { id name } } }
}
"""

# first:250 trips Linear's query-complexity ceiling (max 10000) on a team with many
# labels, so page at 100 and follow the cursor.
Q_LABELS = """
query($teamId: String!, $after: String) {
  team(id: $teamId) {
    labels(first: 100, after: $after) {
      nodes { id name }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

# Page size is a variable because it is environment-dependent, not a constant we can
# pick once: against this workspace, first:50 succeeds and first:100 reliably returns a
# truncated chunked body (IncompleteRead). fetch_existing_titles halves on failure.
Q_ISSUE_TITLES = """
query($teamId: ID!, $after: String, $first: Int!) {
  issues(filter: { team: { id: { eq: $teamId } } }, first: $first, after: $after) {
    nodes { id title }
    pageInfo { hasNextPage endCursor }
  }
}
"""

M_PROJECT = """
mutation($name: String!, $teamIds: [String!]!) {
  projectCreate(input: { name: $name, teamIds: $teamIds }) {
    success project { id name }
  }
}
"""

M_LABEL = """
mutation($name: String!, $teamId: String!) {
  issueLabelCreate(input: { name: $name, teamId: $teamId }) {
    success issueLabel { id name }
  }
}
"""

M_ISSUE = """
mutation($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id identifier title url } }
}
"""

Q_QUEUE = """
query($teamId: ID!, $after: String, $first: Int!) {
  issues(filter: { team: { id: { eq: $teamId } },
                   project: { name: { startsWith: "FinHive" } },
                   state: { type: { nin: ["completed", "canceled"] } } },
         first: $first, after: $after, orderBy: createdAt) {
    nodes { identifier title estimate project { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def write_queue(key: str, team_id: str, path: Path) -> int:
    """Write ops/queue.tsv in build order.

    Creation order IS build order — issues were seeded top-to-bottom from a CSV that
    was already sorted by milestone and dependency, so Linear's own ordering is the
    queue. Column 2 is the identifier; run_builder.sh and orchestrator.sh both cut -f2.
    """
    # These nodes carry title and project, so the body is much larger per row than the
    # id+title pager — it truncates well below first:50. Halve on failure, same as
    # fetch_existing_titles.
    rows, after, page = [], None, 25
    while True:
        try:
            node = gql(Q_QUEUE, {"teamId": team_id, "after": after, "first": page},
                       key=key, retries=2)["issues"]
        except LinearError:
            if page <= 5:
                raise
            page = max(5, page // 2)
            print(f"{YEL}  large page truncated — retrying at first:{page}{RST}", file=sys.stderr)
            continue
        rows.extend(node["nodes"])
        if not node["pageInfo"]["hasNextPage"]:
            break
        after = node["pageInfo"]["endCursor"]
    rows.sort(key=lambda r: int(r["identifier"].rsplit("-", 1)[1]))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# order\tissue\testimate\tproject\ttitle\n")
        fh.write("# regenerate: python3 ops/seed_linear.py --write-queue\n")
        for i, r in enumerate(rows, 1):
            proj = (r["project"] or {}).get("name", "-").replace("\t", " ")
            title = r["title"].replace("\t", " ")
            fh.write(f"{i}\t{r['identifier']}\t{r['estimate'] or 0}\t{proj}\t{title}\n")
    return len(rows)


def fetch_labels(key: str, team_id: str) -> dict[str, str]:
    """name -> id for every label the team can use, following the cursor."""
    out: dict[str, str] = {}
    after = None
    while True:
        node = gql(Q_LABELS, {"teamId": team_id, "after": after}, key=key)["team"]["labels"]
        out.update({l["name"]: l["id"] for l in node["nodes"]})
        if not node["pageInfo"]["hasNextPage"]:
            return out
        after = node["pageInfo"]["endCursor"]


def fetch_existing_titles(key: str, team_id: str, page: int = 50) -> set[str]:
    """Read every issue title in the team, halving the page size when a body truncates.

    Large chunked responses fail in some network paths (proxies, VPNs) while smaller
    ones succeed, and the failure looks like a dead connection rather than a size
    problem. Backing off on page size recovers instead of aborting the whole run.
    """
    titles: set[str] = set()
    after = None
    while True:
        try:
            data = gql(Q_ISSUE_TITLES, {"teamId": team_id, "after": after, "first": page},
                       key=key, retries=2)
        except LinearError:
            if page <= 10:
                raise
            page = max(10, page // 2)
            print(f"{YEL}  large page truncated — retrying at first:{page}{RST}", file=sys.stderr)
            continue
        node = data["issues"]
        titles.update(n["title"].strip() for n in node["nodes"])
        if not node["pageInfo"]["hasNextPage"]:
            return titles
        after = node["pageInfo"]["endCursor"]


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Seed Linear issues from a CSV.")
    ap.add_argument("--apply", action="store_true", help="actually create (default: dry run)")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--milestone", help="only import rows in this Milestone (substring match, e.g. M1)")
    ap.add_argument("--limit", type=int, help="cap the number of issues (useful for a first smoke import)")
    ap.add_argument("--write-queue", action="store_true",
                    help="write ops/queue.tsv from Linear (build order) and exit")
    args = ap.parse_args()

    key = os.environ.get("LINEAR_API_KEY", "").strip()
    team_key = os.environ.get("LINEAR_TEAM_KEY", "").strip()
    if not key:
        print(f"{RED}LINEAR_API_KEY is not set.{RST}", file=sys.stderr)
        print("  Create one at Linear → Settings → Security & access → Personal API keys", file=sys.stderr)
        return 2
    if not team_key:
        print(f"{RED}LINEAR_TEAM_KEY is not set.{RST}", file=sys.stderr)
        print("  This is the issue-id PREFIX (e.g. FIN for FIN-1), not the team name.", file=sys.stderr)
        return 2
    if not args.write_queue and not args.csv.exists():
        print(f"{RED}CSV not found: {args.csv}{RST}", file=sys.stderr)
        return 2

    if args.write_queue:
        teams = gql(Q_TEAM, {"key": team_key}, key=key)["teams"]["nodes"]
        if not teams:
            print(f"{RED}No team with key '{team_key}'.{RST}", file=sys.stderr)
            return 2
        out = REPO / "ops" / "queue.tsv"
        n = write_queue(key, teams[0]["id"], out)
        print(f"  {GRN}wrote{RST} {out.relative_to(REPO)} — {n} open issue(s) in build order")
        return 0

    with args.csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.milestone:
        rows = [r for r in rows if args.milestone.lower() in r["Milestone"].lower()]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print(f"{YEL}No rows to import.{RST}")
        return 0

    teams = gql(Q_TEAM, {"key": team_key}, key=key)["teams"]["nodes"]
    if not teams:
        print(f"{RED}No team with key '{team_key}'.{RST}", file=sys.stderr)
        # Listing what does exist turns a dead end into a next step.
        try:
            avail = gql("{ teams(first: 50) { nodes { key name issueEstimationType } } }",
                        key=key)["teams"]["nodes"]
        except LinearError:
            avail = []
        if avail:
            print("\n  Teams available with this API key:", file=sys.stderr)
            for t in avail:
                est = t.get("issueEstimationType") or "notUsed"
                note = "" if est not in (None, "notUsed") else "  (estimation off)"
                print(f"    LINEAR_TEAM_KEY={t['key']:<8} {t['name']}{note}", file=sys.stderr)
            print(f"\n  {DIM}LINEAR_TEAM_KEY is the issue-id PREFIX (e.g. FIN for FIN-1),{RST}", file=sys.stderr)
            print(f"  {DIM}not the team name. Create a new team in Linear if none of these fit.{RST}", file=sys.stderr)
        return 2
    team = teams[0]
    team_id = team["id"]

    projects = {p["name"]: p["id"] for p in gql(Q_PROJECTS, {"teamId": team_id}, key=key)["team"]["projects"]["nodes"]}
    labels = fetch_labels(key, team_id)
    existing = fetch_existing_titles(key, team_id)

    # Milestones become Linear projects, in first-appearance (build) order.
    want_projects: list[str] = []
    for r in rows:
        name = r["Milestone"].strip()
        if name and name not in want_projects:
            want_projects.append(name)
    want_labels = sorted({
        lbl.strip()
        for r in rows
        for lbl in (r["Labels"].split(",") + [r.get("Workstream", "")])
        if lbl.strip()
    })
    new_projects = [p for p in want_projects if p not in projects]
    new_labels = [l for l in want_labels if l not in labels]
    to_create = [r for r in rows if r["Title"].strip() not in existing]
    skipped = len(rows) - len(to_create)

    mode = f"{GRN}APPLY{RST}" if args.apply else f"{YEL}DRY RUN{RST}"
    print()
    print(f"  {mode}  ·  team {team['key']} — {team['name']}")
    print(f"  {DIM}{'─' * 62}{RST}")
    print(f"  csv          : {args.csv.relative_to(REPO) if args.csv.is_relative_to(REPO) else args.csv}")
    print(f"  rows         : {len(rows)}")
    print(f"  to create    : {len(to_create)}")
    print(f"  already there: {skipped}{'  (skipped by title)' if skipped else ''}")
    print(f"  milestones   : {len(want_projects)} wanted, {len(new_projects)} new")
    for name in want_projects:
        n = sum(1 for r in to_create if r["Milestone"].strip() == name)
        pts = sum(int(r["Estimate"]) for r in to_create if r["Milestone"].strip() == name and r["Estimate"].strip().isdigit())
        print(f"    {DIM}·{RST} {name:<40} {n:>3} issue(s)  {pts:>3} pt")
    print(f"  labels       : {len(want_labels)} wanted, {len(new_labels)} new")
    print(f"  estimation   : {team.get('issueEstimationType') or 'not set'}")
    if team.get("issueEstimationType") in (None, "notUsed"):
        dropped = sum(int(r["Estimate"]) for r in to_create if r["Estimate"].strip().isdigit())
        print(f"  {YEL}! estimation is OFF for team {team['key']} — all {dropped} points will be silently dropped.{RST}")
        print(f"  {DIM}  Fix first: Linear → Settings → Teams → {team['key']} → Estimates{RST}")
        print(f"  {DIM}             set Estimates to Fibonacci (1,2,3,5,8,13), then re-run.{RST}")
        print(f"  {DIM}  Turning it on afterwards does NOT backfill — you would re-enter 147 estimates by hand.{RST}")
    print()

    if not args.apply:
        print(f"  {DIM}first 10 in build order:{RST}")
        for r in to_create[:10]:
            pr = {"1": "Urgent", "2": "High", "3": "Medium", "4": "Low"}.get(r["Priority"].strip(), "None")
            ms = r["Milestone"].split("·")[0].strip()
            print(f"    {DIM}[{ms}/{r.get('Workstream','')}]{RST} {r['Title']}  {DIM}({pr}, {r['Estimate']}pt){RST}")
        if len(to_create) > 10:
            print(f"    {DIM}… and {len(to_create) - 10} more{RST}")
        print()
        print(f"  {DIM}Re-run with --apply to create them.{RST}")
        print()
        return 0

    for name in new_projects:
        res = gql(M_PROJECT, {"name": name, "teamIds": [team_id]}, key=key)["projectCreate"]
        if not res["success"]:
            raise LinearError(f"failed to create project {name!r}")
        projects[name] = res["project"]["id"]
        print(f"  {GRN}+{RST} project  {name}")

    # Label creation can collide with a name the team query did not return — Linear also
    # has workspace-scoped labels, and names are matched case-insensitively. A collision
    # must never abort a 147-issue import, so re-read and carry on.
    for name in new_labels:
        try:
            res = gql(M_LABEL, {"name": name, "teamId": team_id}, key=key)["issueLabelCreate"]
            if res["success"]:
                labels[name] = res["issueLabel"]["id"]
                print(f"  {GRN}+{RST} label    {name}")
                continue
            raise LinearError("issueLabelCreate returned success=false")
        except LinearError as exc:
            labels = fetch_labels(key, team_id)                      # something else owns it
            hit = labels.get(name) or next(
                (v for k, v in labels.items() if k.lower() == name.lower()), None)
            if hit:
                labels[name] = hit
                print(f"  {DIM}={RST} label    {name} {DIM}(already existed){RST}")
            else:
                print(f"  {YEL}!{RST} label    {name} — {exc}; continuing without it",
                      file=sys.stderr)

    created, failed = 0, 0
    for row in to_create:
        title = row["Title"].strip()
        inp: dict = {"teamId": team_id, "title": title, "description": row["Description"].strip()}

        if row["Priority"].strip().isdigit():
            inp["priority"] = int(row["Priority"].strip())
        if row["Estimate"].strip().isdigit() and team.get("issueEstimationType") not in (None, "notUsed"):
            inp["estimate"] = int(row["Estimate"].strip())
        if (pid := projects.get(row["Milestone"].strip())):
            inp["projectId"] = pid
        cells = row["Labels"].split(",") + [row.get("Workstream", "")]
        lids = list(dict.fromkeys(labels[l.strip()] for l in cells if l.strip() in labels))
        if lids:
            inp["labelIds"] = lids

        try:
            res = gql(M_ISSUE, {"input": inp}, key=key)["issueCreate"]
            if not res["success"]:
                raise LinearError("issueCreate returned success=false")
            iss = res["issue"]
            created += 1
            print(f"  {GRN}+{RST} {iss['identifier']:<10} {iss['title'][:64]}")
        except LinearError as exc:
            failed += 1
            print(f"  {RED}✗{RST} {title[:64]}\n      {exc}", file=sys.stderr)
        time.sleep(0.12)  # stay well under Linear's rate limit

    print()
    print(f"  created {created}   failed {failed}   skipped {skipped}")
    if failed:
        print(f"  {DIM}Re-run the same command — created issues are skipped by title.{RST}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LinearError as exc:
        print(f"\n{RED}Linear API error:{RST} {exc}\n", file=sys.stderr)
        sys.exit(3)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)

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

Q_LABELS = """
query($teamId: String!) {
  team(id: $teamId) { labels(first: 250) { nodes { id name } } }
}
"""

Q_ISSUE_TITLES = """
query($teamId: ID!, $after: String) {
  issues(filter: { team: { id: { eq: $teamId } } }, first: 250, after: $after) {
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


def fetch_existing_titles(key: str, team_id: str) -> set[str]:
    titles: set[str] = set()
    after = None
    while True:
        data = gql(Q_ISSUE_TITLES, {"teamId": team_id, "after": after}, key=key)
        page = data["issues"]
        titles.update(n["title"].strip() for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return titles
        after = page["pageInfo"]["endCursor"]


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Seed Linear issues from a CSV.")
    ap.add_argument("--apply", action="store_true", help="actually create (default: dry run)")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--milestone", help="only import rows in this Milestone (substring match, e.g. M1)")
    ap.add_argument("--limit", type=int, help="cap the number of issues (useful for a first smoke import)")
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
    if not args.csv.exists():
        print(f"{RED}CSV not found: {args.csv}{RST}", file=sys.stderr)
        return 2

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
        return 2
    team = teams[0]
    team_id = team["id"]

    projects = {p["name"]: p["id"] for p in gql(Q_PROJECTS, {"teamId": team_id}, key=key)["team"]["projects"]["nodes"]}
    labels = {l["name"]: l["id"] for l in gql(Q_LABELS, {"teamId": team_id}, key=key)["team"]["labels"]["nodes"]}
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
        print(f"  {YEL}! estimation is off for this team — Estimate values will be ignored.{RST}")
        print(f"  {DIM}  Enable at Linear → Settings → Team → Estimates (Fibonacci).{RST}")
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

    for name in new_labels:
        res = gql(M_LABEL, {"name": name, "teamId": team_id}, key=key)["issueLabelCreate"]
        if not res["success"]:
            print(f"  {YEL}!{RST} label    {name} — not created, continuing without it")
            continue
        labels[name] = res["issueLabel"]["id"]
        print(f"  {GRN}+{RST} label    {name}")

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

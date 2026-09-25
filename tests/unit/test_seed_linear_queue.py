"""KCH-232 -- pins ops/seed_linear.py's write_queue ordering.

write_queue used to sort ops/queue.tsv by KCH number alone, so M1.1 issues
(KCH-222+) landed behind the whole paused M1a-M5 web track. queue_sort_key orders
by (milestone_rank, number) instead, rank = [M0, M1.1, M1a, M1b, M2, M3, M4, M5],
derived from the "FinHive <milestone> · <description>" project-name shape
ops/gen_m11_csv.py and the linear_import.csv files already use.

ops/ is not a package (no __init__.py, not installed), so import it the way
tests/unit/test_probe_openrouter.py imports ops/probe_openrouter.py: load the file
by path with importlib rather than `import ops.seed_linear`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_LINEAR = ROOT / "ops" / "seed_linear.py"


def _load_seed_linear():
    spec = importlib.util.spec_from_file_location("seed_linear", SEED_LINEAR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seed_linear = _load_seed_linear()


def _issue(identifier: str, project: str | None) -> dict:
    return {
        "identifier": identifier,
        "title": identifier,
        "estimate": 1,
        "project": {"name": project} if project is not None else None,
    }


def test_m11_issue_sorts_before_m1a_issue_despite_higher_kch_number() -> None:
    # KCH-232 (M1.1) vs KCH-101 (M1a): number-only sort would put 101 first.
    m11 = _issue("KCH-232", "FinHive M1.1 · Ask FinHive")
    m1a = _issue("KCH-101", "FinHive M1a · Local Setup, Login & Encryption")
    ordered = sorted([m1a, m11], key=seed_linear.queue_sort_key)
    assert [r["identifier"] for r in ordered] == ["KCH-232", "KCH-101"], (
        f"M1.1 KCH-232 must sort before M1a KCH-101; got {[r['identifier'] for r in ordered]}"
    )


def test_unknown_project_sorts_last_and_is_not_dropped() -> None:
    m0 = _issue("KCH-1", "FinHive M0 · Foundation & Agent Toolchain")
    m5 = _issue("KCH-2", "FinHive M5 · Completion & Hardening")
    unknown = _issue("KCH-3", "Some Other Workspace Project")
    no_project = _issue("KCH-4", None)
    rows = [m5, unknown, m0, no_project]
    ordered = sorted(rows, key=seed_linear.queue_sort_key)
    # nothing dropped
    assert len(ordered) == len(rows)
    assert {r["identifier"] for r in ordered} == {r["identifier"] for r in rows}
    # both unranked issues sort after every recognised milestone (M0 first, M5 last
    # of the known ranks) but are still present
    tail = {ordered[-1]["identifier"], ordered[-2]["identifier"]}
    got = [r["identifier"] for r in ordered]
    assert tail == {"KCH-3", "KCH-4"}, f"unknown-project issues must sort last, got order {got}"
    assert ordered[0]["identifier"] == "KCH-1"


def test_stable_within_a_project_by_number() -> None:
    a = _issue("KCH-240", "FinHive M1.1 · Ask FinHive")
    b = _issue("KCH-235", "FinHive M1.1 · Ask FinHive")
    c = _issue("KCH-239", "FinHive M1.1 · Ask FinHive")
    ordered = sorted([a, b, c], key=seed_linear.queue_sort_key)
    assert [r["identifier"] for r in ordered] == ["KCH-235", "KCH-239", "KCH-240"]


def _node(identifier: str, project: str | None, *, estimate: int = 1) -> dict:
    """A Q_QUEUE result node, exactly as gql(Q_QUEUE, ...)["issues"]["nodes"] shapes it."""
    return {
        "identifier": identifier,
        "title": f"title for {identifier}",
        "estimate": estimate,
        "project": {"name": project} if project is not None else None,
    }


def test_write_queue_calls_q_queue_and_writes_tsv_in_milestone_order(tmp_path, monkeypatch) -> None:
    # Pins the call site: write_queue must select project.name, or queue_sort_key
    # has nothing to rank by and silently degrades to a number-only sort.
    assert "project { name }" in seed_linear.Q_QUEUE

    nodes = [
        _node("KCH-101", "FinHive M1a · Local Setup, Login & Encryption"),
        _node("KCH-232", "FinHive M1.1 · Ask FinHive"),
    ]
    seen: list[str] = []

    def fake_gql(query, variables=None, *, key, retries=3):
        seen.append(query)
        assert query is seed_linear.Q_QUEUE, "write_queue must query Q_QUEUE, not some other query"
        return {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}

    monkeypatch.setattr(seed_linear, "gql", fake_gql)

    out = tmp_path / "queue.tsv"
    n = seed_linear.write_queue("k", "team-id", out)

    assert n == 2
    assert seen == [seed_linear.Q_QUEUE]
    text = out.read_text(encoding="utf-8")
    data_lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert len(data_lines) == 2
    # M1.1 (KCH-232) must precede M1a (KCH-101) although 101 < 232 numerically.
    assert data_lines[0].split("\t")[1] == "KCH-232"
    assert data_lines[1].split("\t")[1] == "KCH-101"


def test_write_queue_warns_on_unranked_project_but_still_writes_the_row(
    tmp_path, monkeypatch, capsys
) -> None:
    nodes = [_node("KCH-999", "Some Other Workspace Project")]

    def fake_gql(query, variables=None, *, key, retries=3):
        return {"issues": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}

    monkeypatch.setattr(seed_linear, "gql", fake_gql)

    out = tmp_path / "queue.tsv"
    n = seed_linear.write_queue("k", "team-id", out)

    assert n == 1
    err = capsys.readouterr().err
    assert "KCH-999" in err, err
    assert "Some Other Workspace Project" in err, err
    text = out.read_text(encoding="utf-8")
    data_lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert len(data_lines) == 1
    assert data_lines[0].split("\t")[1] == "KCH-999"


def test_full_milestone_order_pinned() -> None:
    # One issue per milestone, reverse-fed in, plus M0 and M1.1 with numbers that
    # would invert the order under a number-only sort.
    issues = [
        _issue("KCH-500", "FinHive M5 · Completion & Hardening"),
        _issue("KCH-400", "FinHive M4 · Multi-User Distribution"),
        _issue("KCH-300", "FinHive M3 · Agent Write, UI Polish & Hosted Infra"),
        _issue("KCH-200", "FinHive M2 · Agent Read-Only"),
        _issue("KCH-150", "FinHive M1b · MVP1 Parity — Read then Write"),
        _issue("KCH-101", "FinHive M1a · Local Setup, Login & Encryption"),
        _issue("KCH-232", "FinHive M1.1 · Ask FinHive"),
        _issue("KCH-1", "FinHive M0 · Foundation & Agent Toolchain"),
    ]
    ordered = [r["identifier"] for r in sorted(issues, key=seed_linear.queue_sort_key)]
    assert ordered == [
        "KCH-1", "KCH-232", "KCH-101", "KCH-150", "KCH-200", "KCH-300", "KCH-400", "KCH-500",
    ]

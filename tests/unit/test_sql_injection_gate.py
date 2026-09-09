"""SQL injection CI grep gate (KCH-84) -- the primary compensating control for
finhive choosing raw SQL (asyncpg) over an ORM.

The gate itself already exists as an emergent property of two earlier commits:
ruff's flake8-bandit ``S`` rules (which include S608, "possible SQL injection
vector through string-based query construction") were selected in
pyproject.toml by KCH-75/76/77, and KCH-82 wired ``ruff check finhive tests``
into the fast-gates CI job that runs on every PR. Nothing here re-implements
that scan -- these tests pin it down so a future edit can't silently narrow
the rule set (e.g. moving "S" to ignore, or scoping the CI step off finhive)
without a test noticing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _ruff_check(tmp_path: Path, code: str) -> subprocess.CompletedProcess[str]:
    target = tmp_path / "sample.py"
    target.write_text(code)
    return subprocess.run(
        ["ruff", "check", "--config", str(PYPROJECT), str(target)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_s608_is_selected_and_not_ignored() -> None:
    lint = tomllib.loads(PYPROJECT.read_text())["tool"]["ruff"]["lint"]
    assert "S" in lint["select"], "flake8-bandit rules (incl. S608) must stay selected"
    assert "S608" not in lint.get("ignore", []), "S608 must not be silenced"


def test_ci_runs_the_rule_set_against_finhive() -> None:
    text = WORKFLOW.read_text()
    assert "ruff check finhive tests" in text


def test_fstring_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'def q(uid):\n    return f"SELECT * FROM users WHERE id = {uid}"\n',
    )
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_percent_formatted_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'def q(uid):\n    return "SELECT * FROM users WHERE id = %s" % (uid,)\n',
    )
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_dot_format_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'def q(uid):\n    return "SELECT * FROM users WHERE id = {}".format(uid)\n',
    )
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_parameterised_sql_constant_is_not_blocked(tmp_path: Path) -> None:
    """The compensating control must not punish the safe pattern it exists to
    push people toward: a placeholder in the literal, values passed separately.
    """
    result = _ruff_check(
        tmp_path,
        (
            "def q(conn, uid):\n"
            '    query = "SELECT * FROM users WHERE id = $1"\n'
            "    return conn.execute(query, uid)\n"
        ),
    )
    assert result.returncode == 0, result.stdout

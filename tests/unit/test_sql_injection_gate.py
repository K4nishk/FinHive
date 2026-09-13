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

import shlex
import subprocess
from pathlib import Path
from typing import Any

import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# The exact, standalone invocation the gate requires -- no extra flags (which
# could silence S608, e.g. ``--ignore=S608`` or ``--exit-zero``).
_RUFF_GATE_COMMAND = ("ruff", "check", "finhive", "tests")
_SHELL_OPERATORS = {"&&", "||", ";", "|"}
# Operators that let a following/preceding command's failure be swallowed
# rather than propagate as the step's exit status.
_STATUS_MASKING_OPERATORS = {"||"}


def _shell_statements(run: str) -> list[tuple[list[str], str | None]]:
    """Tokenise a shell script into ``(command_tokens, operator_after)``
    pairs, using ``shlex`` (with comment stripping) rather than substring
    matching. This means a command that only appears inside a ``#`` comment,
    or as the literal words following ``echo``, tokenises as plain arguments
    of a *different* command rather than as an invocation of ruff.
    """
    try:
        tokens = shlex.split(run, comments=True)
    except ValueError:
        return []
    statements: list[tuple[list[str], str | None]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SHELL_OPERATORS:
            statements.append((current, token))
            current = []
        else:
            current.append(token)
    statements.append((current, None))
    return statements


def _runs_the_ruff_gate_unmasked(run: str) -> bool:
    """True if ``run`` contains a standalone, unmasked invocation of exactly
    ``ruff check finhive tests``: no extra flags, no shell wrapping (echo,
    comments), and no ``||`` swallowing its exit status.
    """
    return any(
        tuple(command) == _RUFF_GATE_COMMAND
        and operator_after not in _STATUS_MASKING_OPERATORS
        for command, operator_after in _shell_statements(run)
    )


def _blocking_ruff_steps(
    workflow: dict[str, Any],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return (job_id, job, step) triples where the ruff step is actually
    capable of blocking a PR: the parent job has no ``if``/``continue-on-error``
    that could skip or tolerate it, the step itself has no ``if``/
    ``continue-on-error`` either, and the shell command is a standalone,
    unmasked ``ruff check finhive tests`` invocation.
    """
    hits: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_id, job in workflow.get("jobs", {}).items():
        if job.get("if") is not None or job.get("continue-on-error", False):
            continue
        for step in job.get("steps", []):
            run = step.get("run", "")
            if not _runs_the_ruff_gate_unmasked(run):
                continue
            if step.get("if") is not None or step.get("continue-on-error", False):
                continue
            hits.append((job_id, job, step))
    return hits


def _ruff_check(
    dest_dir: Path, code: str, filename: str = "sample.py"
) -> subprocess.CompletedProcess[str]:
    target = dest_dir / filename
    target.write_text(code)
    return subprocess.run(
        ["ruff", "check", "--config", str(PYPROJECT), str(target)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_s608_is_selected_in_the_static_config() -> None:
    lint = tomllib.loads(PYPROJECT.read_text())["tool"]["ruff"]["lint"]
    assert "S" in lint["select"], (
        "flake8-bandit rules (incl. S608) must stay selected"
    )
    assert "S608" not in lint.get("ignore", []), "S608 must not be silenced"


def test_s608_is_not_suppressed_for_the_finhive_ci_target() -> None:
    """Check ruff's *effective* configuration for a path inside the CI target
    (``finhive/``), not just the top-level ``[tool.ruff.lint]`` table -- a
    ``per-file-ignores`` entry keyed on e.g. ``finhive/**/*.py`` would silence
    S608 for the package ruff actually lints without changing that table.
    """
    fixture = ROOT / "finhive" / "_kch84_sql_injection_gate_probe.py"
    assert not fixture.exists(), (
        f"refusing to overwrite unexpected file: {fixture}"
    )
    try:
        result = _ruff_check(
            fixture.parent,
            'from __future__ import annotations\n\n\n'
            'def q(uid):\n'
            '    return f"SELECT * FROM users WHERE id = {uid}"\n',
            filename=fixture.name,
        )
    finally:
        fixture.unlink(missing_ok=True)
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_ci_runs_the_rule_set_against_finhive() -> None:
    """The gate is only real if an active step on pull_request actually runs
    it -- a matching string could just as easily sit in a comment, a step (or
    its parent job) gated behind ``if: false``, a step (or its parent job)
    marked ``continue-on-error: true``, or a shell command that swallows
    ruff's exit status (e.g. ``|| true``), any of which would let SQL string
    construction slip past this test.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text())
    assert "pull_request" in workflow[True], (
        "workflow must trigger on pull_request for the gate to run pre-merge"
    )

    assert _blocking_ruff_steps(workflow), (
        "no job runs 'ruff check finhive tests' unconditionally, bound to a "
        "job that also runs unconditionally, without tolerating or masking "
        "failure"
    )


def test_blocking_ruff_steps_rejects_job_level_if() -> None:
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "if": "false",
                "steps": [{"run": "ruff check finhive tests"}],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_job_level_continue_on_error() -> None:
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "continue-on-error": True,
                "steps": [{"run": "ruff check finhive tests"}],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_masked_exit_status() -> None:
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [{"run": "ruff check finhive tests || true"}],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_masking_via_arbitrary_fallback() -> None:
    """``|| true``/``|| exit 0``/``|| :`` aren't the only ways to swallow a
    failure -- any ``||`` fallback (e.g. ``|| echo ignored``) does too, and
    must be rejected the same way.
    """
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [{"run": "ruff check finhive tests || echo ignored"}],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_command_inside_a_comment() -> None:
    """A commented-out invocation must not count as a live gate."""
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [
                    {"run": "# ruff check finhive tests\necho gate disabled"}
                ],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_command_echoed_not_run() -> None:
    """Printing the command's text is not the same as running it."""
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [{"run": "echo ruff check finhive tests"}],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_rejects_flag_that_ignores_s608() -> None:
    """An extra flag (e.g. silencing S608 specifically, or ruff's own
    ``--exit-zero``) makes this a different, non-standalone invocation and
    must not be accepted as the gate.
    """
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [
                    {"run": "ruff check finhive tests --ignore=S608"}
                ],
            }
        }
    }
    assert _blocking_ruff_steps(workflow) == []


def test_blocking_ruff_steps_accepts_unconditional_fatal_step() -> None:
    workflow: dict[str, Any] = {
        "jobs": {
            "fast-gates": {
                "steps": [{"run": "ruff check finhive tests"}],
            }
        }
    }
    hits = _blocking_ruff_steps(workflow)
    assert len(hits) == 1
    assert hits[0][0] == "fast-gates"


def test_fstring_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'from __future__ import annotations\n\n\n'
        'def q(uid):\n    return f"SELECT * FROM users WHERE id = {uid}"\n',
    )
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_percent_formatted_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'from __future__ import annotations\n\n\n'
        'def q(uid):\n'
        '    return "SELECT * FROM users WHERE id = %s" % (uid,)\n',
    )
    assert result.returncode != 0
    assert "S608" in result.stdout


def test_dot_format_sql_constant_is_blocked(tmp_path: Path) -> None:
    result = _ruff_check(
        tmp_path,
        'from __future__ import annotations\n\n\n'
        'def q(uid):\n'
        '    return "SELECT * FROM users WHERE id = {}".format(uid)\n',
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
            "from __future__ import annotations\n"
            "\n\n"
            "def q(conn, uid):\n"
            '    query = "SELECT * FROM users WHERE id = $1"\n'
            "    return conn.execute(query, uid)\n"
        ),
    )
    assert result.returncode == 0, result.stdout

"""Enforcement, not documentation, for the blind-index bypass (KCH-227).

`Query.update()` emits SQL directly and does not fire the `before_update`
mapper event that keeps `_bidx` consistent with `_ct`. A bulk update that
assigns an identity column therefore writes new ciphertext beside a stale
index, and the row stops matching every filter, autocomplete and group
auto-fill -- silently, permanently, with nothing in any log.

The original commit "enforced" this by stating in a docstring that the three
existing bulk methods happen not to touch identity columns. That was true on
the day it was written and enforced nothing: a docstring is a note about
today that the next edit invalidates without noticing.

Two real mechanisms replace it, and this file proves both bite:
  - a runtime guard every bulk payload passes through, and
  - an AST lint so a NEW `Query.update()` that skips the guard fails CI.
"""

from __future__ import annotations

import ast
from importlib.util import find_spec
from pathlib import Path

import pytest


def _missing() -> str | None:
    for mod in ("cryptography", "finhive"):
        try:
            if find_spec(mod) is None:
                return mod
        except (ImportError, ValueError):
            return mod
    return None


_MISSING = _missing()
needs_crypto = pytest.mark.skipif(
    _MISSING is not None,
    reason=f"encryption at rest needs `{_MISSING}` — "
    "pip install -r requirements.txt && pip install -e <repo root>",
)

_REPOSITORIES = Path(__file__).resolve().parents[2] / "loan_manager" / "infrastructure" / "repositories"


class TestRuntimeGuard:
    @needs_crypto
    def test_rejects_a_payload_that_sets_an_identity_column(self):
        from loan_manager.infrastructure.database.blind_index_sync import (
            BlindIndexBypassError,
            assert_no_identity_columns,
        )

        with pytest.raises(BlindIndexBypassError) as exc:
            assert_no_identity_columns(
                {"borrower_name": "someone else", "updated_at": "now"}
            )
        # the message must say what to do instead, not just refuse
        assert "borrower_name" in str(exc.value)
        assert "blind index" in str(exc.value)

    @needs_crypto
    @pytest.mark.parametrize(
        "column",
        ["borrower_name", "borrower_group", "depositor_name", "depositor_group"],
    )
    def test_every_identity_column_is_covered(self, column):
        """All four, not just the one someone remembered to guard."""
        from loan_manager.infrastructure.database.blind_index_sync import (
            BlindIndexBypassError,
            assert_no_identity_columns,
        )

        with pytest.raises(BlindIndexBypassError):
            assert_no_identity_columns({column: "x"})

    @needs_crypto
    def test_allows_the_payloads_the_bulk_methods_actually_use(self):
        """The guard must not block legitimate bulk updates, or it will be
        removed by the next person who hits it."""
        from loan_manager.infrastructure.database.blind_index_sync import (
            assert_no_identity_columns,
        )

        for payload in (
            {"status": "Active", "updated_at": "now"},
            {"giving_date": "d", "due_date": "d", "updated_at": "now"},
            {"is_active": False, "status": "Paidoff", "updated_at": "now"},
        ):
            assert assert_no_identity_columns(payload) == payload

    @needs_crypto
    def test_amount_is_not_guarded_here(self):
        """`amount` is encrypted but has NO blind index (ADR-2.4 forbids one),
        so a bulk update touching it does not desynchronise anything. Guarding
        it would be cargo-culting the identity rule onto a column it does not
        apply to."""
        from loan_manager.infrastructure.database.blind_index_sync import (
            assert_no_identity_columns,
        )

        assert assert_no_identity_columns({"amount": 100}) == {"amount": 100}


class TestBulkUpdateLint:
    """Catches a future `Query.update()` that skips the runtime guard.

    Keyed on the `synchronize_session` keyword, which is unique to
    SQLAlchemy's `Query.update()` -- matching on the method name `update`
    alone would also flag every `dict.update(...)` in the file.
    """

    def _offenders(self) -> list[str]:
        found = []
        for path in sorted(_REPOSITORIES.glob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            guarded: set[int] = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "checked_update"
                ):
                    for inner in ast.walk(node):
                        guarded.add(id(inner))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Attribute) and node.func.attr == "update"):
                    continue
                if not any(kw.arg == "synchronize_session" for kw in node.keywords):
                    continue
                if id(node) in guarded:
                    continue
                found.append(f"{path.name}:{node.lineno}")
        return found

    def test_no_repository_calls_query_update_without_the_guard(self):
        offenders = self._offenders()
        assert not offenders, (
            "these Query.update() calls bypass the blind-index guard and can "
            "silently desynchronise `_bidx` from `_ct`: "
            + ", ".join(offenders)
            + " -- route them through checked_update()"
        )

    def test_the_lint_is_actually_looking_at_something(self):
        """A lint that scans zero files passes forever and proves nothing."""
        scanned = list(_REPOSITORIES.glob("*.py"))
        assert len(scanned) >= 3, f"expected repository modules, found {scanned}"
        sources = "\n".join(p.read_text() for p in scanned)
        assert "checked_update" in sources, (
            "no repository routes a bulk update through the guard -- either "
            "the guard was removed or this lint is pointed at the wrong path"
        )

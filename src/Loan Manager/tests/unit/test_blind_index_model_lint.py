"""CI-blocking rule, ORM half (KCH-227/229, ADR-2.4): no `_bidx` blind-index
column on an amount column in `models.py`.

The repo-root `tests/unit/test_blind_index_lint.py` (finhive's own gate)
statically scans every file in `migrations/` for exactly this mistake --
but it only ever looked at `migrations/`, because until KCH-227/229 a
`_bidx` column could only be introduced by a migration. This issue added
the ORM-level blind index directly to
`loan_manager/infrastructure/database/models.py`, which makes that file a
second, previously-ungated place the same copy-paste mistake (adding
`amount_bidx` the way `borrower_name_bidx` was added) could slip through
with nothing stopping it. This test is that gap closed, kept in the Loan
Manager's own suite -- not the root one, since `models.py` lives under
`src/Loan Manager/` and this is what runs under mvp1-regression.

Parses `models.py` with `ast` rather than grepping text: a text search for
`amount_bidx` is defeated by any renaming or reformatting, while `ast` sees
the real declared attribute names regardless of how the file is styled.
`FORBIDDEN_BLIND_INDEX_COLUMNS` is imported from `finhive.db.blind_index`,
not re-typed here -- a second hard-coded copy of that list is exactly the
kind of thing that quietly drifts out of sync with the real rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _missing() -> str | None:
    """Which dependency of the encryption path is absent, if any.

    Copied verbatim from tests/unit/test_key_provider.py -- see that
    module's docstring for why both `cryptography` and `finhive` must be
    checked, not just `cryptography`.
    """
    from importlib.util import find_spec

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

pytestmark = needs_crypto

if _MISSING is None:
    from finhive.db.blind_index import FORBIDDEN_BLIND_INDEX_COLUMNS

_MODELS_PY = (
    Path(__file__).resolve().parents[2]
    / "loan_manager" / "infrastructure" / "database" / "models.py"
)


def _bidx_attribute_names() -> list[str]:
    """Every `<name>_bidx` mapped attribute declared in any class body of
    `models.py`, by walking the AST's class definitions -- not by matching
    text against the source.
    """
    tree = ast.parse(_MODELS_PY.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            if stmt.target.id.endswith("_bidx"):
                names.append(stmt.target.id)
    return names


def test_forbidden_columns_fixture_is_not_accidentally_empty() -> None:
    """A passing check must mean 'checked and clean', not 'checked
    nothing' -- same safeguard the root-level migration lint gate takes
    on the same fixture.
    """
    assert FORBIDDEN_BLIND_INDEX_COLUMNS


def test_models_py_declares_no_blind_index_on_an_amount_column() -> None:
    bidx_attributes = _bidx_attribute_names()
    assert bidx_attributes, (
        "expected at least one _bidx attribute in models.py -- "
        "this check cannot mean anything if it finds none"
    )
    for attribute in bidx_attributes:
        stem = attribute[: -len("_bidx")]
        assert stem not in FORBIDDEN_BLIND_INDEX_COLUMNS, (
            f"models.py declares {attribute!r} -- ADR-2.4 forbids any "
            f"derived index on amount column {stem!r}"
        )

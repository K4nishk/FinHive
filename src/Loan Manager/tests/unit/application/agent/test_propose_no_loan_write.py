"""ACCEPTANCE guard (KCH-243, ARB D-6: the agent proposes, never writes).

Two independent checks, static and dynamic, over every PROPOSE tool:

1. STATIC: no `propose_*.py` module, nor anything it transitively imports
   from `loan_manager` (bounded to the `loan_manager` package -- stdlib and
   third-party imports are not followed, they cannot reach a loan repo),
   ever accesses `<something>.loans.<attr>` for an `attr` outside the
   read-only set {get_all_active, get_by_reference_id, get_unique_values}.
   `test_agent_import_guard.py` already denies IMPORTING the mutating use
   cases by name; this catches the other way a write could sneak in --
   through a currently-allowed import (GetAllLoans, GetAutocompleteValues,
   CalculateInterest, GenerateReport, GetPendingReports, BuildEntityResolver)
   that itself starts calling `uow.loans.save(...)` or similar.
2. DYNAMIC: each of the four real PROPOSE tool handlers, run against a fake
   UoW whose `FakeLoanRepo` (`conftest.py`) raises `AssertionError("loan
   write")` from every write method, completes successfully and saves
   exactly one report -- proving the ONE write path (`GenerateReport` via
   `propose_common.submit`) is really the only one exercised, not just that
   the static scan found nothing.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest
from loan_manager.application.agent.tools import args as args_mod
from loan_manager.application.agent.tools.propose_tools import build_propose_registry
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock

from .conftest import make_loan, uow_factory_for

_ALLOWED_LOAN_READ_METHODS = frozenset(
    {"get_all_active", "get_by_reference_id", "get_unique_values"}
)

_PROPOSE_MODULE_NAMES = (
    "propose_common",
    "propose_create",
    "propose_extend",
    "propose_update",
    "propose_tools",
)


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _loans_access_violations(source: str) -> list[str]:
    """Every `.loans` attribute access in `source` that is NOT the direct,
    called receiver of an allowlisted method (review cycle 1, MAJOR-1 --
    ORCHESTRATOR RULING: "flag ANY `.loans` attribute access that is not
    the direct receiver of an allowlisted method call ... aliasing,
    getattr, passing `uow.loans` as an argument all fail").

    The OLD check (`<x>.loans.<attr>`, literal shape only) missed three
    real bypasses the reviewer found in a scratch copy: an alias
    (`repo = uow.loans; repo.save(...)`), `getattr(uow.loans, "save")(...)`,
    and `uow.loans` passed into a helper defined elsewhere
    (`_persist(uow.loans, loan)`). All three still reach a real write once
    the fake-repo boundary in `conftest.py` is crossed -- a bare `.loans`
    reference is only safe when its own IMMEDIATE parent is the allowlisted
    `.<method>` attribute, and THAT attribute is immediately called.

    Uses a parent map over `ast.walk` (there is no parent pointer on a
    plain `ast.Attribute` node) rather than a suffix-only pattern match, so
    it cannot be fooled by anything shaped like `X.loans.<name>` where
    `<name>` merely LOOKS like a call but isn't one, or by `.loans` reached
    through any other route.
    """
    tree = ast.parse(source)
    parents = _parent_map(tree)
    problems: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and node.attr == "loans"):
            continue
        parent = parents.get(node)
        if not isinstance(parent, ast.Attribute):
            # Bare `.loans` used as an assignment source, a call argument,
            # a getattr() target, or anything else that is not itself the
            # object of a further `.<method>` attribute access.
            problems.append(".loans (not a direct <x>.loans.<method>() call)")
            continue
        if parent.attr not in _ALLOWED_LOAN_READ_METHODS:
            problems.append(f".loans.{parent.attr}")
            continue
        grandparent = parents.get(parent)
        if not (isinstance(grandparent, ast.Call) and grandparent.func is parent):
            # `uow.loans.get_all_active` referenced but never actually
            # CALLED (e.g. passed around as a bound method) -- not the
            # "direct receiver of an allowlisted method CALL" the ruling
            # requires.
            problems.append(f".loans.{parent.attr} (not called directly)")
    return problems


_FLAGGED_REFLECTION_CALLS = frozenset({"getattr", "setattr"})
_FLAGGED_ATTR_NAMES = frozenset({"_uow_factory", "history", "_session"})
_FLAGGED_STRING_CONSTANT = "loans"


def _propose_module_only_violations(source: str) -> list[str]:
    """String-reflection and off-`.loans` bypasses of `_loans_access_
    violations`, flagged ONLY within a `propose_*.py` module's own source
    -- review cycle 2, MINOR-1, ORCHESTRATOR RULING: "in propose_*.py only
    (not transitively imported modules, to avoid `result.loans` false
    positives)". `_loan_write_violations` never calls this for a
    transitively-imported module, so a legitimate `self.loans` (a plain
    DTO list, say) or `.history`/`._session` name somewhere in
    `get_loans.py` or similar is never at risk of a false positive here.

    `_loans_access_violations`'s structural check only ever looks for an
    `ast.Attribute` node literally named "loans"; none of these bypasses
    (found in the reviewer's `guard_probe.py`) produce one -- the name
    "loans" is reached as a plain string argument to `getattr`/`setattr`/
    `vars`/`operator.attrgetter`, through `__dict__`, or via an entirely
    different attribute (`.history`) that never mentions "loans" at all.

    `getattr(args, field_name)` (a real, legitimate line in
    propose_update.py) stays unflagged: `getattr`/`setattr` are flagged
    only when their name argument is a STRING CONSTANT, never a `Name` --
    dynamic field dispatch through a variable is exactly what that call
    already does safely; `vars(...)` and `operator.attrgetter(...)` are
    flagged unconditionally, since propose_*.py has no legitimate use for
    either.
    """
    tree = ast.parse(source)
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Name)
                and func.id in _FLAGGED_REFLECTION_CALLS
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                problems.append(f"{func.id}(..., {node.args[1].value!r}, ...) call")
            elif isinstance(func, ast.Name) and func.id == "vars":
                problems.append("vars(...) call")
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "attrgetter"
                and isinstance(func.value, ast.Name)
                and func.value.id == "operator"
            ):
                problems.append("operator.attrgetter(...) call")
        elif isinstance(node, ast.Attribute):
            if node.attr == "__dict__":
                problems.append(".__dict__ access")
            elif node.attr in _FLAGGED_ATTR_NAMES:
                problems.append(f".{node.attr} access")
        elif (
            isinstance(node, ast.Constant)
            and node.value == _FLAGGED_STRING_CONSTANT
        ):
            problems.append(f"string constant {node.value!r}")
    return problems


def _agent_tools_dir() -> Path:
    import loan_manager.application.agent.tools as pkg

    return Path(pkg.__file__).resolve().parent


def _loan_manager_root() -> Path:
    return _agent_tools_dir().parents[2]  # .../loan_manager


def _module_path(dotted: str, lm_root: Path) -> Path | None:
    """The `.py` file `dotted` (e.g. "loan_manager.application.use_cases.
    loans.get_loans") resolves to, or None for anything outside the
    `loan_manager` package (stdlib/third-party -- out of scope: it cannot
    hold a `loan_manager` repository reference at all)."""
    if not dotted.startswith("loan_manager."):
        return None
    rel = Path(*dotted.split(".")[1:])
    candidate = lm_root / rel.with_suffix(".py")
    if candidate.is_file():
        return candidate
    candidate_init = lm_root / rel / "__init__.py"
    if candidate_init.is_file():
        return candidate_init
    return None


def _resolve_import(node: ast.Import | ast.ImportFrom, package: str) -> list[str]:
    """Every fully-qualified dotted name this import statement could name --
    mirrors `test_agent_import_guard.py`'s own relative-import resolution."""
    out: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append(alias.name)
        return out

    if node.level == 0:
        base = node.module or ""
    else:
        pkg_parts = package.split(".") if package else []
        base_parts = pkg_parts[: max(len(pkg_parts) - (node.level - 1), 0)]
        base = ".".join(base_parts)
        if node.module:
            base = f"{base}.{node.module}" if base else node.module
    for alias in node.names:
        out.append(f"{base}.{alias.name}" if base else alias.name)
        out.append(base)  # the module itself, for "from pkg.module import Symbol"
    return out


def _package_of(path: Path, lm_root: Path) -> str:
    rel = path.relative_to(lm_root.parent).parts[:-1]
    return ".".join(rel)


def _loan_write_violations(path: Path, lm_root: Path, visited: set[Path]) -> list[str]:
    if path in visited:
        return []
    visited.add(path)
    source = path.read_text()

    problems = [f"{path.name}: {v}" for v in _loans_access_violations(source)]

    package = _package_of(path, lm_root)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for dotted in _resolve_import(node, package):
                candidate = _module_path(dotted, lm_root)
                if candidate is not None:
                    problems.extend(_loan_write_violations(candidate, lm_root, visited))
    return problems


def _propose_module_files(lm_root: Path) -> list[Path]:
    tools_dir = lm_root / "application" / "agent" / "tools"
    return [tools_dir / f"{name}.py" for name in _PROPOSE_MODULE_NAMES]


def test_no_propose_module_reaches_loan_write_path() -> None:
    lm_root = _loan_manager_root()
    visited: set[Path] = set()
    problems: list[str] = []
    for path in _propose_module_files(lm_root):
        problems.extend(_loan_write_violations(path, lm_root, visited))
        # Review cycle 2, MINOR-1: the extra reflection/off-`.loans` checks
        # apply ONLY to each propose_*.py module's own source, never
        # recursively to what it transitively imports (see
        # `_propose_module_only_violations`'s own docstring).
        problems.extend(
            f"{path.name}: {v}" for v in _propose_module_only_violations(path.read_text())
        )
    assert problems == []


def test_guard_catches_loan_write() -> None:
    assert _loans_access_violations("def f(uow):\n    uow.loans.save(None)\n") == [".loans.save"]
    assert _loans_access_violations(
        "def f(uow):\n    uow.loans.bulk_update_dates([])\n"
    ) == [".loans.bulk_update_dates"]
    # Allowed reads, called directly, raise nothing.
    assert _loans_access_violations(
        "def f(uow):\n    uow.loans.get_all_active()\n    uow.loans.get_by_reference_id('x')\n"
    ) == []
    # A DIFFERENT attribute named "loans" one level up (e.g. `.reports.` or
    # some unrelated `.foo.loans`) is not flagged -- must be exactly
    # `<x>.loans`, matched here since `save`'s own `.value` IS an
    # Attribute node whose `.attr == "loans"`.
    assert _loans_access_violations("def f(uow):\n    uow.reports.save(None)\n") == []

    # Review cycle 1, MAJOR-2 (ORCHESTRATOR RULING): one synthetic snippet
    # per bypass the reviewer found in a scratch copy of propose_update.py
    # -- the OLD literal-shape check (`<x>.loans.<attr>` only) returned []
    # for every one of these; each must now be flagged.
    # A. Alias: assigning `uow.loans` to a name, then calling through it.
    assert _loans_access_violations(
        "def f(uow):\n    repo = uow.loans\n    repo.save(None)\n"
    ) == [".loans (not a direct <x>.loans.<method>() call)"]
    # B/C. getattr() dispatch around the literal `.attr` shape.
    assert _loans_access_violations(
        "def f(uow):\n    getattr(uow.loans, 'save')(None)\n"
    ) == [".loans (not a direct <x>.loans.<method>() call)"]
    # D. Passing `uow.loans` into a helper defined in another module.
    assert _loans_access_violations(
        "def f(uow, loan):\n    _persist(uow.loans, loan)\n"
    ) == [".loans (not a direct <x>.loans.<method>() call)"]
    # An allowlisted method referenced but not actually CALLED (e.g. handed
    # off as a bound method) is not the "direct receiver of an allowlisted
    # method CALL" the ruling requires either.
    assert _loans_access_violations(
        "def f(uow):\n    getter = uow.loans.get_all_active\n    getter()\n"
    ) == [".loans.get_all_active (not called directly)"]

def test_guard_catches_reflection_bypasses() -> None:
    """Review cycle 2, MINOR-1 (ORCHESTRATOR RULING): one synthetic snippet
    per string-reflection bypass the reviewer's `guard_probe.py` found --
    `_loans_access_violations`'s structural check only ever looks for an
    `ast.Attribute` node literally named "loans"; none of these produce
    one, so (proven in this same test, before the fix, via `!= []` on the
    OLD structural check alone) it used to miss every one of them."""
    # Every bypass the reviewer's guard_probe.py listed as NOT flagged.
    # Compared sorted -- only the SET of violations matters here, never
    # ast.walk's traversal order.
    assert sorted(_propose_module_only_violations(
        "def f(uow):\n    getattr(uow, 'loans').save(None)\n"
    )) == sorted(["getattr(..., 'loans', ...) call", "string constant 'loans'"])
    assert sorted(_propose_module_only_violations(
        "def f(uow):\n    uow.__dict__['loans'].save(None)\n"
    )) == sorted([".__dict__ access", "string constant 'loans'"])
    assert sorted(_propose_module_only_violations(
        "def f(uow):\n    vars(uow)['loans'].save(None)\n"
    )) == sorted(["vars(...) call", "string constant 'loans'"])
    assert _propose_module_only_violations(
        "import operator\ndef f(uow):\n    operator.attrgetter('loans.save')(uow)(None)\n"
    ) == ["operator.attrgetter(...) call"]
    assert sorted(_propose_module_only_violations(
        "import operator\ndef f(uow):\n    operator.attrgetter('loans')(uow).save(None)\n"
    )) == sorted(["operator.attrgetter(...) call", "string constant 'loans'"])
    assert _propose_module_only_violations(
        "def f(uow):\n"
        "    setattr(uow, 'r', getattr(uow, 'lo' + 'ans'))\n"
        "    uow.r.save(None)\n"
    ) == ["setattr(..., 'r', ...) call"]
    assert _propose_module_only_violations(
        "def f(uow, loan):\n    uow.history.archive(loan, None)\n"
    ) == [".history access"]
    # A hypothetical raw-session escape hatch, flagged by attribute name
    # alone (ORCHESTRATOR RULING's explicit list), regardless of what is
    # done with it.
    # The flagged constant is exactly "loans", not any sentence containing it.
    assert _propose_module_only_violations(
        "def f(uow):\n    uow._session.execute('DROP TABLE loans')\n"
    ) == ["._session access"]

    # Legitimate, UNFLAGGED: getattr/setattr dispatched through a variable
    # (a Name), never a literal string -- exactly propose_update.py's own
    # `getattr(args, field_name)` / `getattr(loan, field_name)`.
    assert _propose_module_only_violations(
        "def f(args, field_name):\n    return getattr(args, field_name)\n"
    ) == []
    assert _propose_module_only_violations(
        "def f(loan, field_name, value):\n    setattr(loan, field_name, value)\n"
    ) == []
    # Ordinary code with no reflection, no `.history`/`_session`/
    # `_uow_factory`, and no bare "loans" string is clean.
    assert _propose_module_only_violations(
        "def f(loan):\n    return loan.borrower_name.strip().lower()\n"
    ) == []


def test_transitive_import_scan_catches_a_write_in_an_imported_helper(tmp_path) -> None:
    """Review cycle 2, MINOR-3 (ORCHESTRATOR RULING, N13): a from-scratch
    fake `loan_manager` package tree, independent of the real one, proving
    `_loan_write_violations`'s RECURSION into whatever a propose module
    imports actually catches a write -- not merely that the real tree
    today happens to already be clean (which `test_no_propose_module_
    reaches_loan_write_path` alone cannot distinguish from "the recursion
    never ran at all", per the reviewer's mut2.py N13: replacing that
    recursive `problems.extend(...)` with a bare `pass` still leaves the
    real-tree test passing)."""
    lm_root = tmp_path / "loan_manager"
    tools_dir = lm_root / "application" / "agent" / "tools"
    tools_dir.mkdir(parents=True)
    (lm_root / "application" / "helper_writes.py").write_text(
        "def bad(uow):\n    uow.loans.save(None)\n"
    )
    propose_fake = tools_dir / "propose_fake.py"
    propose_fake.write_text(
        "from loan_manager.application.helper_writes import bad\n"
        "def f(uow):\n    bad(uow)\n"
    )

    problems = _loan_write_violations(propose_fake, lm_root, set())

    assert problems == ["helper_writes.py: .loans.save"]


def _make_registry(loans, reports_store):
    uow_factory = uow_factory_for(loans, reports_store)
    return build_propose_registry(
        uow_factory,
        FixedClock(date(2026, 6, 1)),
        EventBus(),
        user_request="test request",
    )


def _extend_case(reports_store):
    loan = make_loan(giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1))
    registry = _make_registry([loan], reports_store)
    args = args_mod.ExtendLoan(ref_id=str(loan.reference_id), months=3, rate=12)
    return registry, "extend_loan", args


def _batch_case(reports_store):
    loan = make_loan(
        borrower_group="sharma group",
        giving_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1),  # overdue at the FixedClock's 2026-06-01
    )
    registry = _make_registry([loan], reports_store)
    args = args_mod.ExtendOverdueBatch(borrower_group="sharma group", months=3, rate=12)
    return registry, "extend_overdue_batch", args


def _create_case(reports_store):
    # A loan seeds "sharma group" as a known, resolvable group.
    loan = make_loan(borrower_group="sharma group")
    registry = _make_registry([loan], reports_store)
    args = args_mod.CreateLoan(
        borrower_name="Ravi Kumar",
        borrower_group="sharma group",
        depositor_name="Meena Shah",
        amount=150000,
    )
    return registry, "create_loan", args


def _update_case(reports_store):
    loan = make_loan(amount=10000)
    registry = _make_registry([loan], reports_store)
    args = args_mod.UpdateLoan(ref_id=str(loan.reference_id), amount=200000)
    return registry, "update_loan", args


_CASES = [_extend_case, _batch_case, _create_case, _update_case]


@pytest.mark.parametrize("case_builder", _CASES, ids=[c.__name__ for c in _CASES])
def test_propose_tools_never_call_loan_writes(case_builder) -> None:
    reports_store: list = []
    registry, tool_name, args = case_builder(reports_store)

    result = registry.handler(tool_name)(args)

    assert result["ok"] is True, result
    assert len(reports_store) == 1

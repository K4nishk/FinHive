"""AST import guard for the agent boundary (KCH-235, review cycle 1 fix).

Enforces, statically, that nothing under loan_manager/application/agent/**
(and loan_manager/application/use_cases/agent/**, if that package exists)
imports:

  - PySide6, sqlalchemy, sqlite3, importlib, builtins — layering: no UI, ORM
    or dynamic import/exec mechanism leaks into the application layer's
    agent package. `exec(...)` and `eval(...)` calls are denied outright for
    the same reason `importlib.import_module` and `__import__` are: a
    dynamically-built statement/expression is invisible to every other
    check here.
  - loan_manager.infrastructure, loan_manager.presentation,
    loan_manager.application.interfaces.unit_of_work — wrong direction of
    dependency for Clean Architecture (the agent boundary talks to use
    cases, never to a repository/session interface or a UI module directly).
  - the mutating use cases (create/update/extend/delete_loan, mark_paidoff,
    recompute_statuses, import_loans, approve/decline_report), by their
    fully-qualified module path, however it is spelled: absolute
    (`from loan_manager.application.use_cases.loans import create_loan`),
    relative (`from ...use_cases.loans import create_loan`), or a direct
    dotted import (`import loan_manager.application.use_cases.loans.create_loan`).
  - `from loan_manager.application.use_cases import loans` (and the same
    form for `reports`, `data`, or for `use_cases` itself — e.g.
    `from loan_manager.application import use_cases` or, written relatively,
    `from .. import use_cases`) — importing a use_cases (sub)package as a
    namespace object exposes every mutating use case inside it
    (`loans.create_loan(...)`, or transitively `use_cases.loans.create_loan`)
    just as much as importing the name directly, and a plain per-name deny
    list cannot see through that; reject the (sub)package import itself
    instead. generate_report and get_reports (both reads) stay importable
    by their own full module path — only the bare `reports`/`data`/
    `use_cases` namespace import is denied, not what is inside it.
  - any `importlib.import_module(...)` or `__import__(...)` call — a dynamic
    import name is not visible to this static check at all, so it is banned
    outright rather than pattern-matched.

  generate_report is the one exception, PROPOSE path: agent proposals are
  report batches (ARB D-8, D-2 human approval); D-6 forbids loan WRITES, not
  proposal writes, and generate_report only builds a report, it does not
  mutate a loan. approve_report/decline_report (the human-approval step
  itself) stay denied — the agent proposes, it never approves its own
  proposal.

Relative imports are resolved against the FILE'S OWN PACKAGE before being
checked — `from ...use_cases.loans import create_loan` written inside
`agent/tools/args.py` (4 path segments deep) and `from ..use_cases.loans
import create_loan` written inside `agent/tool_registry.py` (3 path segments
deep) both resolve to the identical fully-qualified
`loan_manager.application.use_cases.loans.create_loan`, and either is
caught. A suffix-only match (the review-cycle-1 BLOCKER: matching only the
last two dotted segments regardless of how many dots or which absolute path
they resolved to) cannot tell a correctly-scoped relative import from one
that resolves somewhere else entirely, so it is not used here.
"""
from __future__ import annotations

import ast
from pathlib import Path

AGENT_PACKAGE_RELATIVE_ROOTS = (
    "loan_manager/application/agent",
    "loan_manager/application/use_cases/agent",
)

# Denied by EQUAL-OR-DOTTED-PREFIX: the fully-qualified name is denied, and so
# is anything nested under it (`sqlalchemy` denies `sqlalchemy.orm.Session`;
# `loan_manager.infrastructure` denies `loan_manager.infrastructure.db.engine`
# AND the bare `from loan_manager import infrastructure`, since that resolves
# to the fully-qualified name `loan_manager.infrastructure` itself).
_DENIED_PREFIXES: frozenset[str] = frozenset(
    {
        "PySide6",
        "sqlalchemy",
        "sqlite3",
        "importlib",
        "builtins",
        "loan_manager.infrastructure",
        "loan_manager.presentation",
        "loan_manager.application.interfaces.unit_of_work",
        "loan_manager.application.use_cases.loans.create_loan",
        "loan_manager.application.use_cases.loans.update_loan",
        "loan_manager.application.use_cases.loans.extend_loan",
        "loan_manager.application.use_cases.loans.delete_loan",
        "loan_manager.application.use_cases.loans.mark_paidoff",
        "loan_manager.application.use_cases.loans.recompute_statuses",
        "loan_manager.application.use_cases.data.import_loans",
        "loan_manager.application.use_cases.reports.approve_report",
        "loan_manager.application.use_cases.reports.decline_report",
    }
)

# Denied only by EXACT match: each use_cases (sub)package itself, imported
# bare as a namespace object, is denied — but a PREFIX match here would also
# wrongly catch the READ use cases living in the very same packages
# (`...loans.get_loans`, `...loans.get_autocomplete`, `...reports.
# generate_report`, `...reports.get_reports`), which stay allowed by their
# own full module path.
_DENIED_EXACT: frozenset[str] = frozenset(
    {
        "loan_manager.application.use_cases",
        "loan_manager.application.use_cases.loans",
        "loan_manager.application.use_cases.reports",
        "loan_manager.application.use_cases.data",
    }
)


def _is_denied(fq_name: str) -> bool:
    if fq_name in _DENIED_EXACT:
        return True
    return any(fq_name == prefix or fq_name.startswith(prefix + ".") for prefix in _DENIED_PREFIXES)


def _lm_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "loan_manager"
        if (candidate / "application").is_dir():
            return candidate
    raise FileNotFoundError(f"loan_manager/ package not found above {here}")


def _agent_files() -> list[Path]:
    lm_parent = _lm_root().parent
    files: list[Path] = []
    for rel in AGENT_PACKAGE_RELATIVE_ROOTS:
        d = lm_parent / rel
        if d.is_dir():
            files.extend(sorted(d.rglob("*.py")))
    return files


def _package_of(path: Path, lm_root: Path) -> str:
    """Dotted package name of the directory containing `path` — the name
    Python's relative-import machinery would use as that module's
    `__package__` (e.g. loan_manager/application/agent/tools/args.py ->
    "loan_manager.application.agent.tools")."""
    rel = path.parent.relative_to(lm_root.parent)
    return ".".join(rel.parts)


def _resolve_module(module: str, level: int, package: str) -> str:
    """Fully-qualified dotted module name for an ImportFrom's (module, level)
    given the importing file's own dotted `package`. level=0 is absolute
    (module is already fully qualified). level=1 is "from this package";
    each extra level strips one more trailing segment off `package` first."""
    if level == 0:
        return module
    pkg_parts = package.split(".") if package else []
    base_parts = pkg_parts[: max(len(pkg_parts) - (level - 1), 0)]
    base = ".".join(base_parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


_DENIED_BARE_CALLS: frozenset[str] = frozenset({"__import__", "exec", "eval"})


def _dynamic_import_violations(tree: ast.AST) -> list[str]:
    """`importlib.import_module(...)`, `__import__(...)`, `exec(...)` and
    `eval(...)` calls — banned outright, regardless of argument, since a
    dynamically-built import name or code string is invisible to every
    other check here."""
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _DENIED_BARE_CALLS:
            problems.append(f"{func.id}(...)")
        elif (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
        ):
            problems.append(f"importlib.{func.attr}(...)")
    return problems


def violations(source: str, package: str = "") -> list[str]:
    """Every forbidden import or dynamic-import call in `source`, as the
    fully-qualified dotted name (or call description) that was denied.
    `package` is the dotted package of the file `source` is imagined to live
    in (see `_package_of`) — required to resolve any relative import in it."""
    problems: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_denied(alias.name):
                    problems.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_module(node.module or "", node.level, package)
            for alias in node.names:
                fq_name = f"{module}.{alias.name}" if module else alias.name
                if _is_denied(fq_name):
                    problems.append(fq_name)
    problems.extend(_dynamic_import_violations(tree))
    return problems


def test_guard_scans_files() -> None:
    """The scan actually finds the real agent module files (a guard that
    silently scans zero files would pass for the wrong reason)."""
    files = _agent_files()
    names = {f.name for f in files}
    assert "tool_registry.py" in names
    assert "args.py" in names


def test_no_violations_in_real_agent_code() -> None:
    lm_root = _lm_root()
    for path in _agent_files():
        found = violations(path.read_text(), package=_package_of(path, lm_root))
        assert found == [], f"{path}: {found}"


def test_guard_catches_violation() -> None:
    # Root-level denies, absolute — no package context needed (level=0).
    assert violations("import sqlalchemy\n") == ["sqlalchemy"]
    assert violations("import PySide6.QtWidgets\n") == ["PySide6.QtWidgets"]
    assert violations("import sqlite3\n") == ["sqlite3"]
    assert violations("from sqlalchemy.orm import Session\n") == ["sqlalchemy.orm.Session"]
    assert violations("from loan_manager.infrastructure.db import engine\n") == [
        "loan_manager.infrastructure.db.engine"
    ]
    assert violations("from loan_manager.presentation.main_window import MainWindow\n") == [
        "loan_manager.presentation.main_window.MainWindow"
    ]
    assert violations("from loan_manager import infrastructure\n") == [
        "loan_manager.infrastructure"
    ]
    assert violations("from loan_manager import presentation\n") == [
        "loan_manager.presentation"
    ]
    assert violations(
        "from loan_manager.application.interfaces.unit_of_work import UnitOfWork\n"
    ) == ["loan_manager.application.interfaces.unit_of_work.UnitOfWork"]

    # Mutating use cases, absolute.
    assert violations(
        "from loan_manager.application.use_cases.loans import create_loan\n"
    ) == ["loan_manager.application.use_cases.loans.create_loan"]
    assert violations(
        "from loan_manager.application.use_cases.loans.create_loan import CreateLoan\n"
    ) == ["loan_manager.application.use_cases.loans.create_loan.CreateLoan"]
    assert violations("import loan_manager.application.use_cases.loans.create_loan\n") == [
        "loan_manager.application.use_cases.loans.create_loan"
    ]
    # The subpackage-as-namespace bypass: `loans.create_loan(...)`.
    assert violations("from loan_manager.application.use_cases import loans\n") == [
        "loan_manager.application.use_cases.loans"
    ]
    # ... but the READ use cases in the SAME package stay allowed.
    assert (
        violations("from loan_manager.application.use_cases.loans.get_loans import GetAllLoans\n")
        == []
    )
    assert (
        violations(
            "from loan_manager.application.use_cases.loans import get_autocomplete\n"
        )
        == []
    )

    # Mutating use cases, relative — resolved against the file's own package.
    # A file at agent/tools/*.py (package has 4 segments) needs 3 dots to
    # reach loan_manager.application; a file at agent/*.py (3 segments)
    # needs 2. Both must resolve to the identical fully-qualified name.
    assert violations(
        "from ...use_cases.loans import create_loan\n",
        package="loan_manager.application.agent.tools",
    ) == ["loan_manager.application.use_cases.loans.create_loan"]
    assert violations(
        "from ...use_cases.loans.create_loan import CreateLoan\n",
        package="loan_manager.application.agent.tools",
    ) == ["loan_manager.application.use_cases.loans.create_loan.CreateLoan"]
    assert violations(
        "from ..use_cases.loans import create_loan\n",
        package="loan_manager.application.agent",
    ) == ["loan_manager.application.use_cases.loans.create_loan"]
    assert violations(
        "from ..use_cases.data import import_loans\n",
        package="loan_manager.application.agent",
    ) == ["loan_manager.application.use_cases.data.import_loans"]
    assert violations(
        "from ..use_cases.reports import approve_report\n",
        package="loan_manager.application.agent",
    ) == ["loan_manager.application.use_cases.reports.approve_report"]
    assert violations(
        "from ..use_cases.reports import decline_report\n",
        package="loan_manager.application.agent",
    ) == ["loan_manager.application.use_cases.reports.decline_report"]
    # generate_report is the documented PROPOSE exception (ARB D-8/D-2;
    # D-6 forbids loan WRITES, not proposal writes) and stays allowed — see
    # module docstring.
    assert (
        violations(
            "from ..use_cases.reports import generate_report\n",
            package="loan_manager.application.agent",
        )
        == []
    )

    # Namespace imports of a use_cases (sub)package expose every mutating
    # use case inside it just as much as importing the name directly.
    assert violations("from loan_manager.application.use_cases import reports\n") == [
        "loan_manager.application.use_cases.reports"
    ]
    assert violations("from loan_manager.application.use_cases import data\n") == [
        "loan_manager.application.use_cases.data"
    ]
    assert violations("from loan_manager.application import use_cases\n") == [
        "loan_manager.application.use_cases"
    ]
    assert violations(
        "from .. import use_cases\n", package="loan_manager.application.agent"
    ) == ["loan_manager.application.use_cases"]
    # ... but generate_report/get_reports stay importable by full module path.
    assert (
        violations("from loan_manager.application.use_cases.reports import generate_report\n")
        == []
    )
    assert (
        violations("from loan_manager.application.use_cases.reports import get_reports\n") == []
    )
    assert (
        violations(
            "from loan_manager.application.use_cases.reports.generate_report "
            "import GenerateReport\n"
        )
        == []
    )
    assert (
        violations(
            "from loan_manager.application.use_cases.reports.get_reports import GetReports\n"
        )
        == []
    )

    # Dynamic imports and dynamic execution — banned outright, no import
    # statement even present.
    assert violations('importlib.import_module("sqlalchemy")\n') == ["importlib.import_module(...)"]
    assert violations('__import__("sqlalchemy")\n') == ["__import__(...)"]
    assert violations("import importlib\n") == ["importlib"]
    assert violations('exec("x = 1")\n') == ["exec(...)"]
    assert violations('eval("1 + 1")\n') == ["eval(...)"]
    assert violations('import builtins\nbuiltins.__import__("x")\n') == ["builtins"]

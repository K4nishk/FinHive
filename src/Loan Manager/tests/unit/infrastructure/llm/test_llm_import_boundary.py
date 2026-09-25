"""KCH-234: AST enforcement, not documentation, for the LLM import boundary
-- mirrors the pattern in tests/unit/test_blind_index_enforcement.py
(KCH-227). A docstring saying "only openai_compat_client.py imports openai"
is a note the next edit invalidates without noticing; this fails CI instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

LM_ROOT = Path(__file__).resolve().parents[4] / "loan_manager"
ALLOWED_OPENAI_IMPORTER = Path("infrastructure/llm/openai_compat_client.py")

_FORBIDDEN_IN_PORT = (
    "loan_manager.infrastructure",
    "PySide6",
    "sqlalchemy",
    "sqlite3",
    "openai",
    "httpx",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _dynamic_import_offenses(path: Path) -> list[str]:
    """`importlib.import_module("openai")` or `__import__("openai")` would
    smuggle the SDK into a module past the static `import openai` check
    above -- flag any use of either mechanism at all outside the one file
    allowed to touch the SDK, since there is no legitimate reason for any
    other `loan_manager/**` module to import anything dynamically.

    Also flags any use of the `builtins` module at all (review round 2, item
    4): `builtins.__import__(...)` and `getattr(builtins, "__import__")(...)`
    both reach the real `__import__` builtin without the literal token
    `__import__` appearing as a called `Name`, so the direct-call check above
    alone would miss them. There is no legitimate reason for any
    `loan_manager/**` module outside the SDK boundary to reference `builtins`
    at all, so any import of it or any attribute/name reference to it is
    flagged, whatever it is then used for."""
    tree = ast.parse(path.read_text(), filename=str(path))
    offenses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "importlib" or alias.name.startswith("importlib.")
            for alias in node.names
        ):
            offenses.append(f"{path.name}:{node.lineno}: imports importlib")
        elif isinstance(node, ast.Import) and any(alias.name == "builtins" for alias in node.names):
            offenses.append(f"{path.name}:{node.lineno}: imports builtins")
        elif isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "importlib" or node.module.startswith("importlib.")
        ):
            offenses.append(f"{path.name}:{node.lineno}: imports from importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            offenses.append(f"{path.name}:{node.lineno}: imports from builtins")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                offenses.append(f"{path.name}:{node.lineno}: calls __import__()")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                offenses.append(f"{path.name}:{node.lineno}: calls importlib.import_module()")
        elif isinstance(node, ast.Name) and node.id == "builtins":
            offenses.append(f"{path.name}:{node.lineno}: references the name 'builtins'")
    return offenses


def _package_parts(path: Path, root: Path) -> tuple[str, ...]:
    """The dotted package (not module) `path` lives in, as a tuple of parts,
    with `root`'s own basename as the leading component -- e.g. for
    `<root>/infrastructure/llm/openai_compat_client.py` with
    `root=.../loan_manager`, `("loan_manager", "infrastructure", "llm")`.
    An `__init__.py` file's own dotted name IS the package it defines."""
    rel = path.relative_to(root.parent)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
        return tuple(parts)
    return tuple(parts[:-1])


def _resolve_import_from(path: Path, node: ast.ImportFrom, root: Path) -> str | None:
    """The fully-dotted module `node` imports from, resolving `node.level`
    dots against `path`'s own package the way Python's real import system
    does -- so `from .openai_compat_client import OpenAI` (module=
    "openai_compat_client", level=1) resolves the same as the equivalent
    absolute `from loan_manager.infrastructure.llm.openai_compat_client
    import OpenAI` (level=0) would. Returns `None` if a relative import
    reaches above `root`'s own top package (nothing in this tree can name)."""
    if node.level == 0:
        return node.module
    package = list(_package_parts(path, root))
    up = node.level - 1
    if up:
        if up > len(package):
            return None
        package = package[: len(package) - up]
    if node.module:
        package = package + node.module.split(".")
    return ".".join(package)


def _reexports_openai_class(path: Path, root: Path = LM_ROOT) -> list[str]:
    """`from ...openai_compat_client import OpenAI` -- absolute OR relative
    (`from .openai_compat_client import OpenAI`, `from ..llm.
    openai_compat_client import OpenAI`, ...) -- would hand a caller the raw
    SDK class through the one module allowed to hold it, defeating the point
    of confining `import openai` to that module in the first place (review
    round 2, item 4: the original check only matched the fully-qualified
    absolute spelling and missed every relative form)."""
    tree = ast.parse(path.read_text(), filename=str(path))
    offenses = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not any(alias.name == "OpenAI" for alias in node.names):
            continue
        resolved = _resolve_import_from(path, node, root)
        if resolved == "loan_manager.infrastructure.llm.openai_compat_client":
            offenses.append(f"{path.name}:{node.lineno}")
    return offenses


def test_only_openai_compat_client_imports_openai() -> None:
    offenders = []
    for path in sorted(LM_ROOT.rglob("*.py")):
        imports = _imported_modules(path)
        if any(name == "openai" or name.startswith("openai.") for name in imports):
            offenders.append(path.relative_to(LM_ROOT))

    assert offenders == [ALLOWED_OPENAI_IMPORTER], (
        "only infrastructure/llm/openai_compat_client.py may import the "
        f"openai SDK; found it imported in: {offenders}"
    )


def test_llm_port_imports_no_infrastructure() -> None:
    path = LM_ROOT / "application" / "agent" / "llm_port.py"
    imports = _imported_modules(path)

    banned = [
        name
        for name in imports
        if any(name == prefix or name.startswith(prefix + ".") for prefix in _FORBIDDEN_IN_PORT)
    ]
    assert not banned, f"llm_port.py is a pure port and must not import: {banned}"


def test_the_lint_is_actually_looking_at_something() -> None:
    """A lint scanning zero files passes forever and proves nothing."""
    scanned = list(LM_ROOT.rglob("*.py"))
    assert len(scanned) >= 20, f"expected the whole loan_manager tree, found {scanned}"


def test_no_dynamic_import_bypasses_the_openai_boundary() -> None:
    """MINOR (review round 1, item 10): a static `import openai` check alone
    cannot catch `importlib.import_module("openai")` or `__import__("openai")`
    -- ban the mechanism entirely outside the one allowed file, rather than
    trying to detect the string "openai" inside a dynamic call."""
    offenders = []
    for path in sorted(LM_ROOT.rglob("*.py")):
        if path.relative_to(LM_ROOT) == ALLOWED_OPENAI_IMPORTER:
            continue
        offenders.extend(_dynamic_import_offenses(path))
    assert not offenders, f"dynamic import usage outside openai_compat_client.py: {offenders}"


def _http_client_seam_offenses(path: Path) -> list[str]:
    """`_http_client=` on `OpenAICompatClient.__init__` is a test-only seam
    (KCH-234 review round 2, item 7) -- no call anywhere under
    `loan_manager/**` may pass it; only `tests/**` (outside this scan's root)
    may."""
    tree = ast.parse(path.read_text(), filename=str(path))
    offenses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "_http_client":
                    offenses.append(f"{path.name}:{node.lineno}")
    return offenses


def test_no_production_module_uses_the_http_client_test_seam() -> None:
    """MINOR (review round 2, item 7): `_http_client` exists so a test can
    inject an `httpx.MockTransport` without opening a socket -- no real code
    path within `loan_manager/**` may pass it. `tests/**` is a separate tree
    from `LM_ROOT` and is not scanned here, so this only ever constrains
    production code."""
    offenders = []
    for path in sorted(LM_ROOT.rglob("*.py")):
        offenders.extend(_http_client_seam_offenses(path))
    assert not offenders, f"production code uses the test-only _http_client seam: {offenders}"


def test_no_module_reexports_the_openai_class_from_the_client() -> None:
    """MINOR (review round 1, item 10): nothing may pull the raw `OpenAI`
    class back out of openai_compat_client.py -- that would let a caller
    build its own unmapped-exception SDK client, defeating the boundary."""
    offenders = []
    for path in sorted(LM_ROOT.rglob("*.py")):
        if path.relative_to(LM_ROOT) == ALLOWED_OPENAI_IMPORTER:
            continue
        offenders.extend(_reexports_openai_class(path))
    assert not offenders, f"re-exports the OpenAI SDK class from the client: {offenders}"


def _write_synthetic_llm_tree(tmp_path: Path, sneaky_source: str) -> tuple[Path, Path]:
    """Builds `<tmp_path>/loan_manager/infrastructure/llm/{__init__.py,
    openai_compat_client.py, sneaky.py}` -- a minimal stand-in for the real
    tree, so `_reexports_openai_class` can be exercised against a planted
    offending file without ever writing one into the real `loan_manager/**`
    (which would itself be the violation this lint exists to catch).
    Returns (synthetic root, sneaky.py's path)."""
    root = tmp_path / "loan_manager"
    llm_dir = root / "infrastructure" / "llm"
    llm_dir.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "infrastructure" / "__init__.py").write_text("")
    (llm_dir / "__init__.py").write_text("")
    (llm_dir / "openai_compat_client.py").write_text("class OpenAI:\n    pass\n")
    sneaky = llm_dir / "sneaky.py"
    sneaky.write_text(sneaky_source)
    return root, sneaky


def test_relative_reexport_of_openai_class_is_flagged(tmp_path: Path) -> None:
    """MAJOR (review round 2, item 4): the original check only matched the
    fully-qualified absolute module string
    "loan_manager.infrastructure.llm.openai_compat_client" -- a relative
    `from .openai_compat_client import OpenAI` (the natural way to write this
    re-export from a sibling module) has `node.module ==
    "openai_compat_client"` and `node.level == 1`, which never equalled that
    absolute string, so the scanner silently passed it. Planted in a
    synthetic tree (tmp_path), deleted with it at teardown -- never written
    into the real tree."""
    root, sneaky = _write_synthetic_llm_tree(
        tmp_path, "from .openai_compat_client import OpenAI\n"
    )

    offenders = _reexports_openai_class(sneaky, root=root)

    assert offenders, "relative re-export of OpenAI was not flagged"


def test_dotted_relative_reexport_of_openai_class_is_flagged(tmp_path: Path) -> None:
    """Same gap, one level up: `from ..llm.openai_compat_client import
    OpenAI` (level=2, module="llm.openai_compat_client")."""
    root = tmp_path / "loan_manager"
    infra_dir = root / "infrastructure"
    llm_dir = infra_dir / "llm"
    other_dir = infra_dir / "other"
    other_dir.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (infra_dir / "__init__.py").write_text("")
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / "__init__.py").write_text("")
    (llm_dir / "openai_compat_client.py").write_text("class OpenAI:\n    pass\n")
    (other_dir / "__init__.py").write_text("")
    sneaky = other_dir / "sneaky.py"
    sneaky.write_text("from ..llm.openai_compat_client import OpenAI\n")

    offenders = _reexports_openai_class(sneaky, root=root)

    assert offenders, "dotted relative re-export of OpenAI was not flagged"


def test_absolute_reexport_of_openai_class_is_still_flagged(tmp_path: Path) -> None:
    """The pre-existing absolute-form detection must keep working once the
    relative-resolution logic is layered in front of it."""
    root, sneaky = _write_synthetic_llm_tree(
        tmp_path,
        "from loan_manager.infrastructure.llm.openai_compat_client import OpenAI\n",
    )

    offenders = _reexports_openai_class(sneaky, root=root)

    assert offenders, "absolute re-export of OpenAI was not flagged"


def test_unrelated_relative_import_is_not_flagged(tmp_path: Path) -> None:
    """A relative import that has nothing to do with openai_compat_client
    must not be a false positive."""
    root, sneaky = _write_synthetic_llm_tree(tmp_path, "from . import settings\n")

    offenders = _reexports_openai_class(sneaky, root=root)

    assert offenders == []


def test_builtins_attribute_import_bypass_is_flagged(tmp_path: Path) -> None:
    """MAJOR (review round 2, item 4): `builtins.__import__("openai")`
    reaches the real `__import__` builtin without the literal token
    `__import__` ever appearing as a called `ast.Name` -- the pre-existing
    direct-call check alone misses it entirely. Planted in a scratch file
    under tmp_path, gone at teardown."""
    offender = tmp_path / "sneaky.py"
    offender.write_text("import builtins\nbuiltins.__import__('openai')\n")

    offenses = _dynamic_import_offenses(offender)

    assert offenses, "builtins.__import__ bypass was not flagged"


def test_builtins_getattr_bypass_is_flagged(tmp_path: Path) -> None:
    """Same bypass, one more layer of indirection:
    `getattr(builtins, "__import__")("openai")` -- still just a reference to
    the name `builtins`, which must be flagged regardless of how it is then
    used."""
    offender = tmp_path / "sneaky.py"
    offender.write_text(
        "import builtins\n"
        "getattr(builtins, '__import__')('openai')\n"
    )

    offenses = _dynamic_import_offenses(offender)

    assert offenses, "getattr(builtins, '__import__') bypass was not flagged"

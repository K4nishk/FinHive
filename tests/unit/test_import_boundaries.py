"""Import-linter architecture boundary contracts (KCH-85) — ARD v2.0.0 §5
says the service boundaries are enforced by CI, not just drawn in a
diagram. This pins the three contracts down: calc-service stays pure,
agent-service never touches SQL directly, and domain never reaches into
infrastructure or presentation.

The behavioural tests actually run `lint-imports` against a throwaway
package that mirrors the shape of a contract, so a violating import is
proven to fail the gate and a compliant one is proven not to -- not just
"the toml has the right keys". They skip (not fail) when `lint-imports`
is not on PATH, e.g. offline dev sandboxes without network access to
install it; CI installs it via `pip install -e ".[dev]"` and always runs
them for real.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

requires_import_linter = pytest.mark.skipif(
    shutil.which("lint-imports") is None,
    reason=(
        "import-linter not installed "
        "(no network access to install it here)"
    ),
)


def _contracts() -> list[dict]:
    cfg = tomllib.loads(PYPROJECT.read_text())
    return cfg["tool"]["importlinter"]["contracts"]


def _contract(name: str) -> dict:
    return next(c for c in _contracts() if c["name"] == name)


def test_root_package_is_finhive() -> None:
    cfg = tomllib.loads(PYPROJECT.read_text())
    assert cfg["tool"]["importlinter"]["root_package"] == "finhive"


def test_calc_service_is_pure_contract() -> None:
    contract = _contract("calc-service is pure")
    assert contract["type"] == "forbidden"
    assert contract["source_modules"] == ["finhive.calc"]
    for forbidden in ["finhive.db", "finhive.agent", "httpx", "asyncpg"]:
        assert forbidden in contract["forbidden_modules"]


def test_agent_never_touches_sql_directly_contract() -> None:
    contract = _contract("agent never touches SQL directly")
    assert contract["type"] == "forbidden"
    assert contract["source_modules"] == ["finhive.agent"]
    for forbidden in ["asyncpg", "finhive.db.raw"]:
        assert forbidden in contract["forbidden_modules"]


def test_domain_boundary_contract() -> None:
    contract = _contract(
        "domain does not depend on infrastructure or presentation"
    )
    assert contract["type"] == "forbidden"
    assert contract["source_modules"] == ["finhive.domain"]
    for forbidden in ["finhive.db", "api"]:
        assert forbidden in contract["forbidden_modules"]


def test_ci_runs_lint_imports() -> None:
    text = WORKFLOW.read_text()
    assert "lint-imports" in text


def test_lint_imports_runs_before_the_node_toolchain() -> None:
    """Cheapest-first tier (KCH-82): a Python static-analysis gate must
    not wait on npm ci / node setup to fail fast.
    """
    text = WORKFLOW.read_text()
    assert text.index("lint-imports") < text.index("setup-node")


def _write_pkg(tmp_path: Path, root: str, modules: dict[str, str]) -> None:
    """Lay out `root/<dotted module>.py` files with the given source for
    each entry."""
    (tmp_path / root).mkdir()
    (tmp_path / root / "__init__.py").write_text("")
    for dotted, source in modules.items():
        parts = dotted.split(".")
        pkg_dir = tmp_path / root
        for part in parts[:-1]:
            pkg_dir = pkg_dir / part
            pkg_dir.mkdir(exist_ok=True)
            init = pkg_dir / "__init__.py"
            if not init.exists():
                init.write_text("")
        (pkg_dir / f"{parts[-1]}.py").write_text(source)


def _run_lint_imports(
    tmp_path: Path, config: str
) -> subprocess.CompletedProcess[str]:
    (tmp_path / "pyproject.toml").write_text(config)
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    return subprocess.run(
        ["lint-imports"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


CALC_CONFIG = """
[tool.importlinter]
root_package = "pkg"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "calc-service is pure"
type = "forbidden"
source_modules = ["pkg.calc"]
forbidden_modules = ["pkg.db", "pkg.agent", "httpx", "asyncpg"]
"""


@requires_import_linter
def test_calc_importing_db_is_blocked(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "calc.interest": "import pkg.db\n",
            "db": "",
            "agent": "",
        },
    )
    result = _run_lint_imports(tmp_path, CALC_CONFIG)
    assert result.returncode != 0, result.stdout


@requires_import_linter
def test_calc_without_forbidden_imports_passes(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "calc.interest": "from decimal import Decimal\n\nDecimal('1')\n",
            "db": "",
            "agent": "",
        },
    )
    result = _run_lint_imports(tmp_path, CALC_CONFIG)
    assert result.returncode == 0, result.stdout


@requires_import_linter
def test_calc_importing_httpx_is_blocked(tmp_path: Path) -> None:
    """Regression for KCH-85 round 2: without
    include_external_packages = true, import-linter excludes external
    packages from the graph and this forbidden import would pass
    incorrectly."""
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "calc.client": "import httpx\n",
            "db": "",
            "agent": "",
        },
    )
    result = _run_lint_imports(tmp_path, CALC_CONFIG)
    assert result.returncode != 0, result.stdout


AGENT_CONFIG = """
[tool.importlinter]
root_package = "pkg"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "agent never touches SQL directly"
type = "forbidden"
source_modules = ["pkg.agent"]
forbidden_modules = ["asyncpg", "pkg.db.raw"]
"""


@requires_import_linter
def test_agent_importing_db_raw_is_blocked(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "agent.tool": "import pkg.db.raw\n",
            "db.raw": "",
        },
    )
    result = _run_lint_imports(tmp_path, AGENT_CONFIG)
    assert result.returncode != 0, result.stdout


@requires_import_linter
def test_agent_importing_asyncpg_is_blocked(tmp_path: Path) -> None:
    """Regression for KCH-85 round 2: without
    include_external_packages = true, import-linter excludes external
    packages from the graph and this forbidden import would pass
    incorrectly."""
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "agent.tool": "import asyncpg\n",
            "db.raw": "",
        },
    )
    result = _run_lint_imports(tmp_path, AGENT_CONFIG)
    assert result.returncode != 0, result.stdout


@requires_import_linter
def test_agent_using_typed_db_module_passes(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "agent.tool": "import pkg.db.typed\n",
            "db.raw": "",
            "db.typed": "",
        },
    )
    result = _run_lint_imports(tmp_path, AGENT_CONFIG)
    assert result.returncode == 0, result.stdout


DOMAIN_CONFIG = """
[tool.importlinter]
root_package = "pkg"

[[tool.importlinter.contracts]]
name = "domain does not depend on infrastructure or presentation"
type = "forbidden"
source_modules = ["pkg.domain"]
forbidden_modules = ["pkg.db", "api"]
"""


@requires_import_linter
def test_domain_importing_infrastructure_is_blocked(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "domain.entity": "import pkg.db\n",
            "db": "",
        },
    )
    result = _run_lint_imports(tmp_path, DOMAIN_CONFIG)
    assert result.returncode != 0, result.stdout


@requires_import_linter
def test_domain_staying_pure_passes(tmp_path: Path) -> None:
    _write_pkg(
        tmp_path,
        "pkg",
        {
            "domain.entity": (
                "from dataclasses import dataclass\n\n\n"
                "@dataclass\nclass Loan:\n    pass\n"
            ),
            "db": "",
        },
    )
    result = _run_lint_imports(tmp_path, DOMAIN_CONFIG)
    assert result.returncode == 0, result.stdout

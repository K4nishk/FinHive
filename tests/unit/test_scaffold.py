"""The scaffold's own contract.

pytest exits 5 ("no tests collected") on an empty suite, so a scaffold with no test
fails its own acceptance criterion. These assertions are not filler: they fail if
someone deletes a package directory or breaks the layer boundaries the ARD depends
on, which is exactly the kind of change that looks harmless in a diff.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ARD v2.0.0 Appendix A. Layer directories are listed individually rather than
# globbed so that deleting one is a test failure, not a silently smaller tree.
REQUIRED_DIRS = [
    "api",
    "finhive/domain/entities",
    "finhive/domain/value_objects",
    "finhive/domain/services",
    "finhive/domain/repositories",
    "finhive/domain/events",
    "finhive/calc",
    "finhive/application/use_cases",
    "finhive/application/dtos",
    "finhive/db",
    "finhive/agent/tools",
    "finhive/retrieval",
    "web/src",
    "web/content",
    "dbt/models/staging",
    "dbt/models/marts",
    "migrations",
    "evals/golden",
    "tests/unit",
    "tests/integration",
    "tests/e2e",
]


def test_required_directories_exist() -> None:
    missing = [d for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
    assert not missing, f"missing scaffold directories: {missing}"


def test_python_packages_are_importable() -> None:
    """Every finhive/ directory needs __init__.py or imports resolve inconsistently."""
    pkg_dirs = [
        p for p in (ROOT / "finhive").rglob("*")
        if p.is_dir() and "__pycache__" not in p.parts
    ]
    missing = [
        str(p.relative_to(ROOT)) for p in [ROOT / "finhive", *pkg_dirs]
        if not (p / "__init__.py").exists()
    ]
    assert not missing, f"packages without __init__.py: {missing}"


def test_coverage_floor_is_not_below_target() -> None:
    """The ARD sets 85%. This ratchets up, never down."""
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert cfg["tool"]["coverage"]["report"]["fail_under"] >= 85


def test_domain_and_calc_are_strictly_typed() -> None:
    """The layers carrying the business rules must stay under strict mypy."""
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())
    overrides = cfg["tool"]["mypy"]["overrides"]
    strict = next(o for o in overrides if "finhive.domain.*" in o["module"])
    assert strict["disallow_untyped_defs"] is True
    assert "finhive.calc.*" in strict["module"]

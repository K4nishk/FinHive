"""Scoring metrics and the ratchet (KCH-248 ships the seam; KCH-250 fills it).

`METRICS` maps a metric name to `(case, run) -> float` in [0, 1]. It is empty
here on purpose: registering a metric is KCH-250's job. `baseline.json` holds
each metric's floor; `ratchet` fails a run that falls below it, and a floor is
only ever raised by editing the file in a reviewed change.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

from tests.evals.harness import CaseRun
from tests.evals.schema import Case

BASELINE_PATH = Path(__file__).parent / "baseline.json"

Metric = Callable[[Case, CaseRun], float]
METRICS: dict[str, Metric] = {}


def run_metrics(case: Case, run: CaseRun) -> dict[str, float]:
    return {name: metric(case, run) for name, metric in METRICS.items()}


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, float]:
    return {k: float(v) for k, v in json.loads(path.read_text())["metrics"].items()}


def ratchet(current: Mapping[str, float], baseline: Mapping[str, float]) -> list[str]:
    """Regressions against `baseline`: a metric below its floor, or missing
    from `current` altogether (a dropped metric is not a pass)."""
    failures = []
    for name, floor in sorted(baseline.items()):
        if name not in current:
            failures.append(f"{name}: missing (baseline {floor})")
        elif current[name] < floor:
            failures.append(f"{name}: {current[name]} < baseline {floor}")
    return failures

"""Record a live cassette for an eval case -- OWNER-ONLY (KCH-248).

    OPENROUTER_API_KEY=... python -m tests.evals.record smoke-001 [smoke-002 ...]

Runs the case against the live model once and writes `cassettes/<id>.json`
with `meta.source = "recorded"`. Refuses (exit 2, before any client is built)
when `CI` is set or `OPENROUTER_API_KEY` is not: cloud agents and pipelines
never record (ARB U-3); a recording spends money and is reviewed like code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import date

from loan_manager.application.agent.system_prompt import PROMPT_VERSION

from tests.evals.conftest import LIVE_KEY_ENV
from tests.evals.fixture import use_ephemeral_key_ring
from tests.evals.harness import cassette_path, completion_to_dict, run_case
from tests.evals.schema import load_cases


def refusal_reason(environ: Mapping[str, str]) -> str | None:
    if environ.get("CI"):
        return "refusing to record: CI is set. Cassettes are recorded by the owner, locally."
    if not environ.get(LIVE_KEY_ENV):
        return f"refusing to record: {LIVE_KEY_ENV} is not set."
    return None


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = os.environ if environ is None else environ
    reason = refusal_reason(environ)
    if reason:
        sys.stderr.write(reason + "\n")
        return 2

    parser = argparse.ArgumentParser(prog="python -m tests.evals.record")
    parser.add_argument("case_ids", nargs="+")
    args = parser.parse_args(argv)
    cases = {c.id: c for c in load_cases()}
    unknown = [i for i in args.case_ids if i not in cases]
    if unknown:
        sys.stderr.write(f"unknown case id(s): {', '.join(unknown)}\n")
        return 2

    from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient
    from loan_manager.infrastructure.llm.settings import load_llm_settings

    use_ephemeral_key_ring()
    client = OpenAICompatClient(load_llm_settings())
    for case_id in args.case_ids:
        run = run_case(cases[case_id], client)
        payload = {
            "meta": {
                "source": "recorded",
                "prompt_version": PROMPT_VERSION,
                "model": run.completions[0].model if run.completions else "unknown",
                "recorded_on": date.today().isoformat(),
            },
            "completions": [completion_to_dict(c) for c in run.completions],
        }
        cassette_path(case_id).write_text(json.dumps(payload, indent=2) + "\n")
        sys.stdout.write(f"recorded {case_id}: {run.result.outcome.value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

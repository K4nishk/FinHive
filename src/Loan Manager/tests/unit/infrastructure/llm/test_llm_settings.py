"""KCH-234: LLMSettings loads the repo's own data/settings.json and rejects
an out-of-range value -- the guard against `rate=0.12`-style unit confusion
(ARB, ops/probe_openrouter.py:148) applies to temperature too: fail closed,
not silently clamp."""

from __future__ import annotations

import pytest
from loan_manager.config import SETTINGS_FILE
from loan_manager.infrastructure.llm.settings import LLMSettings, load_llm_settings
from pydantic import ValidationError


def test_repo_settings_json_loads_llm_block() -> None:
    settings = load_llm_settings(SETTINGS_FILE)

    assert settings.model == "qwen/qwen-2.5-72b-instruct"
    assert settings.api_key_env == "OPENROUTER_API_KEY"
    assert str(settings.base_url).startswith("https://openrouter.ai/api/v1")
    assert settings.temperature == pytest.approx(0.1)
    assert settings.max_steps == 6
    assert settings.timeout_s == 60


def test_out_of_range_temperature_rejected() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(
            base_url="https://openrouter.ai/api/v1",
            model="qwen/qwen-2.5-72b-instruct",
            api_key_env="OPENROUTER_API_KEY",
            temperature=3,
            max_steps=6,
            timeout_s=60,
        )

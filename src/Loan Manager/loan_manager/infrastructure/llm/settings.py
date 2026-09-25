"""KCH-234: typed load of `data/settings.json["llm"]` (JSON, not TOML —
`config.py:SETTINGS_FILE` is the single settings file the rest of the app
already reads and writes)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from loan_manager.config import SETTINGS_FILE


class LLMSettings(BaseModel):
    """`extra="ignore"` so `measured_usd_per_call`, `measured_on`,
    `measured_with` and `quirks` — human-facing provenance fields, not
    request parameters — pass through `settings.json` without needing a
    field here. `frozen=True`: a loaded settings object is a value, never
    mutated after `load_llm_settings()` returns it."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    base_url: HttpUrl
    model: str
    api_key_env: str
    # 0 is a legal temperature (ORCH: some providers coerce it, but rejecting
    # it here would be enforcing a provider quirk in a field that is not
    # provider-specific); data/settings.json ships 0.1.
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_steps: int = Field(ge=1, le=20)
    timeout_s: float = Field(gt=0, le=300)


def load_llm_settings(path: Path = SETTINGS_FILE) -> LLMSettings:
    data = json.loads(Path(path).read_text())
    return LLMSettings(**data["llm"])

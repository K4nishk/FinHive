"""Offline guard and lane wiring for the eval suite (KCH-248).

Every test here is an `eval`. Those NOT marked `llm` run in the offline lane
(pull requests, no secret): sockets and the OpenAI client are blocked, so a
harness bug or a stray un-recorded call fails loudly instead of quietly
reaching a provider. `llm` tests are the opt-in live lane and skip unless
`OPENROUTER_API_KEY` is set (`live_skip_reason`).
"""
from __future__ import annotations

import os
import socket
from collections.abc import Iterable, Mapping

import pytest

LIVE_KEY_ENV = "OPENROUTER_API_KEY"


class NetworkBlockedError(AssertionError):
    """Raised by any socket connect or OpenAI client build in the offline lane."""


def live_skip_reason(marker_names: Iterable[str], environ: Mapping[str, str]) -> str | None:
    """Why a test must be skipped, or `None`. Only `llm` tests can be skipped
    here, and only for want of the key."""
    if "llm" not in set(marker_names):
        return None
    if not environ.get(LIVE_KEY_ENV):
        return f"{LIVE_KEY_ENV} not set -- live eval lane needs a key"
    return None


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "tests/evals/" not in item.nodeid.replace("\\", "/"):
            continue
        item.add_marker(pytest.mark.eval)
        reason = live_skip_reason(
            (m.name for m in item.iter_markers()), os.environ
        )
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))


def _blocked(*_args, **_kwargs):
    raise NetworkBlockedError("network access is blocked in the offline eval lane")


@pytest.fixture(autouse=True)
def _offline_guard(request, monkeypatch):
    if request.node.get_closest_marker("llm"):
        yield
        return
    import openai

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(openai.OpenAI, "__init__", _blocked)
    yield

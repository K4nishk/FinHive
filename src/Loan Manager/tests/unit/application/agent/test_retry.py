"""Slice 1 (D-18): retrying a model call through cold starts, busy servers and
dropped connections, and stopping between retries.

Owner decisions, 2026-10-09:
- about 2 minutes of retrying when the server answers but is not ready
  (timeout, 429, 5xx -- a gateway's 503 while the model loads);
- fail fast, about 5 seconds, when there is no connection at all (the box is
  off, or this machine is not on its network);
- a Stop request takes effect during a wait, not after it.
"""
from __future__ import annotations

import threading
import time

import pytest
from loan_manager.application.agent.llm_port import (
    LLMConfigError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from loan_manager.application.agent.retry import (
    DEFAULT_RETRY_POLICY,
    CancelToken,
    FailureKind,
    RetriesExhaustedError,
    RetryNotice,
    RetryPolicy,
    TurnCancelledError,
    call_with_retry,
    classify,
)

INSTANT = RetryPolicy(busy_delays_s=(0, 0, 0), unreachable_delays_s=(0, 0), max_wait_s=120)


class Script:
    """Raises the scripted errors in order, then returns `result`."""

    def __init__(self, *errors: Exception, result: str = "ok") -> None:
        self.errors = list(errors)
        self.result = result
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


def _run(call, *, policy=INSTANT, cancel=None, monotonic=time.monotonic):
    notices: list[RetryNotice] = []
    result = call_with_retry(
        call,
        policy=policy,
        cancel=cancel or CancelToken(),
        monotonic=monotonic,
        on_wait=notices.append,
    )
    return result, notices


# ── classification ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (LLMUnavailableError("refused", status=None), FailureKind.UNREACHABLE),
        (LLMTimeoutError("slow"), FailureKind.BUSY),
        (LLMUnavailableError("loading", status=503), FailureKind.BUSY),
        (LLMUnavailableError("bad gateway", status=502), FailureKind.BUSY),
        (LLMUnavailableError("gateway timeout", status=504), FailureKind.BUSY),
        (LLMUnavailableError("server error", status=500), FailureKind.BUSY),
        (LLMUnavailableError("rate limited", status=429), FailureKind.BUSY),
        (LLMUnavailableError("request timeout", status=408), FailureKind.BUSY),
    ],
)
def test_transient_failures_are_classified(exc, kind) -> None:
    assert classify(exc) is kind


@pytest.mark.parametrize(
    "exc",
    [
        LLMUnavailableError("bad key", status=401),
        LLMUnavailableError("forbidden", status=403),
        LLMUnavailableError("no such model", status=404),
        LLMUnavailableError("bad request", status=400),
        LLMResponseError("malformed"),
        LLMConfigError("no key"),
    ],
)
def test_permanent_failures_are_never_retried(exc) -> None:
    """Retrying a wrong key or a missing model only makes the user wait for
    the same answer."""
    assert classify(exc) is None
    call = Script(exc)
    with pytest.raises(type(exc)):
        _run(call)
    assert call.calls == 1


# ── retrying ──────────────────────────────────────────────────────────────


def test_a_busy_server_is_retried_until_it_answers() -> None:
    call = Script(LLMUnavailableError("loading", status=503), LLMTimeoutError("slow"))

    result, notices = _run(call)

    assert result == "ok"
    assert call.calls == 3
    assert [(n.kind, n.attempt) for n in notices] == [
        (FailureKind.BUSY, 2),
        (FailureKind.BUSY, 3),
    ]


def test_a_dropped_connection_on_a_warm_server_recovers() -> None:
    call = Script(LLMUnavailableError("reset", status=None))
    result, notices = _run(call)
    assert result == "ok"
    assert [n.kind for n in notices] == [FailureKind.UNREACHABLE]


def test_an_unreachable_server_fails_fast() -> None:
    call = Script(*[LLMUnavailableError("refused", status=None)] * 10)

    with pytest.raises(RetriesExhaustedError) as excinfo:
        _run(call)

    assert excinfo.value.kind is FailureKind.UNREACHABLE
    assert call.calls == 1 + len(INSTANT.unreachable_delays_s)


def test_a_server_that_stays_busy_gives_up_after_its_schedule() -> None:
    call = Script(*[LLMUnavailableError("loading", status=503)] * 10)

    with pytest.raises(RetriesExhaustedError) as excinfo:
        _run(call)

    assert excinfo.value.kind is FailureKind.BUSY
    assert call.calls == 1 + len(INSTANT.busy_delays_s)


def test_no_wait_starts_that_would_end_past_the_max_wait() -> None:
    now = [0.0]
    policy = RetryPolicy(busy_delays_s=(0, 0, 0), unreachable_delays_s=(0,), max_wait_s=10)

    class SlowBusy:
        calls = 0

        def __call__(self):
            self.calls += 1
            now[0] += 6  # each attempt takes 6 s before failing
            raise LLMTimeoutError("slow")

    call = SlowBusy()
    with pytest.raises(RetriesExhaustedError):
        _run(call, policy=policy, monotonic=lambda: now[0])
    assert call.calls == 2  # 6 s, then 12 s: past 10 s, so no third attempt


def test_notices_carry_the_delay_about_to_be_waited() -> None:
    policy = RetryPolicy(busy_delays_s=(0.01, 0.02), unreachable_delays_s=(0.01,), max_wait_s=5)
    call = Script(LLMTimeoutError("a"), LLMTimeoutError("b"))
    _, notices = _run(call, policy=policy)
    assert [n.delay_s for n in notices] == [0.01, 0.02]


# ── stopping ──────────────────────────────────────────────────────────────


def test_a_stop_before_the_call_sends_nothing() -> None:
    cancel = CancelToken()
    cancel.cancel()
    call = Script()
    with pytest.raises(TurnCancelledError):
        _run(call, cancel=cancel)
    assert call.calls == 0


def test_a_stop_during_a_wait_ends_it_at_once() -> None:
    policy = RetryPolicy(busy_delays_s=(30,), unreachable_delays_s=(30,), max_wait_s=120)
    cancel = CancelToken()
    call = Script(LLMTimeoutError("slow"))
    threading.Timer(0.2, cancel.cancel).start()

    started = time.monotonic()
    with pytest.raises(TurnCancelledError):
        _run(call, policy=policy, cancel=cancel)

    assert time.monotonic() - started < 5
    assert call.calls == 1


# ── the owner's numbers ───────────────────────────────────────────────────


def test_default_policy_matches_the_owner_decisions() -> None:
    policy = DEFAULT_RETRY_POLICY
    assert policy.max_wait_s == 120  # "about 2 min"
    busy = sum(policy.busy_delays_s)
    assert 60 <= busy <= policy.max_wait_s  # rides out a 30-90 s model load
    assert sum(policy.unreachable_delays_s) <= 5  # "fail fast"

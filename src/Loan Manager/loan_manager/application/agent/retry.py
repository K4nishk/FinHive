"""Retrying one model call through cold starts, busy servers and dropped
connections, and stopping between retries (slice 1 of D-18).

`openai_compat_client` sets `max_retries=0` so that this loop, not the SDK,
owns retrying: the user sees each wait, and a Stop request ends it at once.
`RunAgentTurn` wraps every `LLMPort.complete` call in `call_with_retry`. A
retry re-sends the same messages, which already passed `assert_no_plaintext`;
it is not a step, so it never spends the six-step budget.

Two kinds of transient failure, with the owner's numbers (2026-10-09):

- BUSY: the server answered but is not ready -- a timeout, 408/409/425/429 or
  a 5xx. A gateway in front of vLLM answers 503 while the model loads, which
  is what makes a cold start look BUSY rather than UNREACHABLE (vLLM itself
  refuses connections until loaded). Retried for about 2 minutes.
- UNREACHABLE: no answer at all -- connection refused, no route, DNS. The box
  is off or this machine is not on its network. Retried briefly, about 5
  seconds, which also rides out one dropped connection to a warm server.

Anything else (401/403/404, a malformed response, a missing key) is permanent:
retrying would only make the user wait for the same answer.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from loan_manager.application.agent.llm_port import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)

T = TypeVar("T")

_BUSY_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class FailureKind(str, Enum):
    UNREACHABLE = "unreachable"
    BUSY = "busy"


@dataclass(frozen=True)
class RetryPolicy:
    """Delays between attempts, per kind of failure, and an overall cap.

    `max_wait_s` is measured from the first attempt: no wait starts that would
    end past it, so a slow failing attempt cannot stretch the total."""

    busy_delays_s: tuple[float, ...] = (2, 4, 8, 16, 30, 30)
    unreachable_delays_s: tuple[float, ...] = (1, 3)
    max_wait_s: float = 120

    def delays_for(self, kind: FailureKind) -> tuple[float, ...]:
        return self.busy_delays_s if kind is FailureKind.BUSY else self.unreachable_delays_s


DEFAULT_RETRY_POLICY = RetryPolicy()


@dataclass(frozen=True)
class RetryNotice:
    """Sent before each wait: why, which attempt comes next, how long until it."""

    kind: FailureKind
    attempt: int
    delay_s: float


class RetriesExhaustedError(LLMError):
    """Every retry for `kind` was spent, or the next wait would pass `max_wait_s`."""

    def __init__(self, kind: FailureKind) -> None:
        super().__init__(f"model call still failing ({kind.value}) after retrying")
        self.kind = kind


class TurnCancelledError(Exception):
    """The user pressed Stop. Not an `LLMError`: nothing failed."""


class CancelToken:
    """Set from the UI thread, read on the worker thread."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        """Sleep up to `seconds`; return True at once if Stop is pressed."""
        return self._event.wait(seconds)


def classify(exc: LLMError) -> FailureKind | None:
    """The kind of transient failure `exc` is, or None when it is permanent."""
    if isinstance(exc, LLMTimeoutError):
        return FailureKind.BUSY
    if isinstance(exc, LLMUnavailableError):
        if exc.status is None:
            return FailureKind.UNREACHABLE
        if exc.status in _BUSY_STATUSES:
            return FailureKind.BUSY
    return None


def call_with_retry(
    call: Callable[[], T],
    *,
    policy: RetryPolicy,
    cancel: CancelToken,
    monotonic: Callable[[], float],
    on_wait: Callable[[RetryNotice], None],
) -> T:
    """`call()`, retried per `policy` on transient failures.

    Raises `TurnCancelledError` if Stop is pressed before an attempt or during
    a wait, `RetriesExhaustedError` when retrying gives up, and any permanent
    `LLMError` unchanged."""
    started = monotonic()
    retries = {kind: 0 for kind in FailureKind}
    attempt = 1
    while True:
        if cancel.cancelled:
            raise TurnCancelledError()
        try:
            return call()
        except LLMError as exc:
            kind = classify(exc)
            if kind is None:
                raise
            delays = policy.delays_for(kind)
            used = retries[kind]
            if used >= len(delays) or monotonic() - started + delays[used] > policy.max_wait_s:
                raise RetriesExhaustedError(kind) from exc
            retries[kind] = used + 1
            attempt += 1
            on_wait(RetryNotice(kind, attempt, delays[used]))
            if cancel.wait(delays[used]):
                raise TurnCancelledError() from None

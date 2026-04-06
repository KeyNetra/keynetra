"""Shared resilience helpers for service orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TypeVar

ResultT = TypeVar("ResultT")

_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def with_timeout(func: Callable[[], ResultT], *, timeout_seconds: float) -> ResultT:
    future = _EXECUTOR.submit(func)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"operation timed out after {timeout_seconds} seconds") from exc


def retry(
    func: Callable[[], ResultT], *, attempts: int, base_delay_seconds: float = 0.05
) -> ResultT:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return func()
        except Exception as exc:  # noqa: PERF203
            last_error = exc
            if attempt >= max(1, attempts):
                break
            time.sleep(base_delay_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error

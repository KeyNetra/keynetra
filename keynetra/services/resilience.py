"""Shared resilience helpers for service orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Lock
from typing import TypeVar

from keynetra.config.settings import Settings
from keynetra.observability.metrics import (
    observe_resilience_executor_pressure,
    record_backend_timeout,
)

ResultT = TypeVar("ResultT")

_EXECUTORS: dict[int, ThreadPoolExecutor] = {}
_EXECUTORS_LOCK = Lock()


def _get_executor(settings: Settings | None = None) -> ThreadPoolExecutor:
    max_workers = settings.resolved_resilience_executor_workers() if settings is not None else 4
    with _EXECUTORS_LOCK:
        executor = _EXECUTORS.get(max_workers)
        if executor is None:
            executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="keynetra-resilience",
            )
            _EXECUTORS[max_workers] = executor
        return executor


# Backward-compatible default executor used by tests and non-configured callers.
_EXECUTOR = _get_executor()


def with_timeout(
    func: Callable[[], ResultT], *, timeout_seconds: float, settings: Settings | None = None
) -> ResultT:
    executor = _EXECUTOR if settings is None else _get_executor(settings)
    queue_depth = getattr(getattr(executor, "_work_queue", None), "qsize", lambda: 0)()
    observe_resilience_executor_pressure(queue_depth=queue_depth)
    future = executor.submit(func)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        record_backend_timeout(operation="threadpool")
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

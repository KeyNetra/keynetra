from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("typer")
from keynetra.cli import app
from typer.testing import CliRunner


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


async def _fake_post(self, *args, **kwargs) -> _FakeResponse:  # type: ignore[override]
    await asyncio.sleep(0)
    return _FakeResponse()


def test_benchmark_command(monkeypatch) -> None:
    monkeypatch.setattr("keynetra.cli.httpx.AsyncClient.post", _fake_post)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--api-key",
            "testkey",
            "--requests",
            "2",
            "--concurrency",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "p50(ms)" in result.stdout

#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from pathlib import Path

import httpx

P95_BUDGET_MS = 500.0
CACHE_HIT_RATIO_MIN = 0.10


def _parse_p95(path: Path) -> float:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("Name") == "Aggregated":
                return float(row.get("95%", "0") or "0")
    return 0.0


def _cache_hit_ratio(metrics_text: str) -> float:
    hit = 0.0
    miss = 0.0
    hit_pattern = re.compile(r'^keynetra_cache_hits_total\{cache_type="decision"\}\s+([0-9.]+)$')
    miss_pattern = re.compile(r'^keynetra_cache_misses_total\{cache_type="decision"\}\s+([0-9.]+)$')
    for line in metrics_text.splitlines():
        mh = hit_pattern.match(line)
        if mh:
            hit = float(mh.group(1))
            continue
        mm = miss_pattern.match(line)
        if mm:
            miss = float(mm.group(1))
    denom = hit + miss
    return (hit / denom) if denom > 0 else 0.0


def main() -> int:
    p95 = _parse_p95(Path("/tmp/locust_stats.csv"))
    if p95 > P95_BUDGET_MS:
        print(f"p95 latency budget failed: {p95:.2f}ms > {P95_BUDGET_MS:.2f}ms")
        return 1
    metrics = httpx.get("http://127.0.0.1:8000/metrics", timeout=5.0).text
    ratio = _cache_hit_ratio(metrics)
    if ratio < CACHE_HIT_RATIO_MIN:
        print(f"decision cache hit ratio budget failed: {ratio:.3f} < {CACHE_HIT_RATIO_MIN:.3f}")
        return 1
    print(f"load budgets passed: p95={p95:.2f}ms cache_hit_ratio={ratio:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

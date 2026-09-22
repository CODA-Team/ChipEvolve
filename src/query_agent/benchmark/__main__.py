"""Thin CLI entry point for the deterministic benchmark."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .phase2 import Phase2BenchmarkRunner
from .runner import BenchmarkRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic benchmark")
    parser.add_argument("benchmark_dir", type=Path)
    args = parser.parse_args(argv)
    if (args.benchmark_dir / "benchmark.json").read_text(encoding="utf-8").find(
        "Phase II"
    ) >= 0:
        report = Phase2BenchmarkRunner().run(args.benchmark_dir)
    else:
        report = BenchmarkRunner().run(args.benchmark_dir)
    print(f"total cases: {report.total}")
    print(f"passed: {report.passed}")
    print(f"failed: {report.failed}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

from pathlib import Path

from query_agent.benchmark.phase3 import Phase3BenchmarkRunner


def test_phase3_design_object_benchmark_is_deterministic(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "benchmarks" / "phase3" / "benchmark.json"
    target = tmp_path / "benchmark.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    report = Phase3BenchmarkRunner().run(tmp_path)
    assert report.total >= 8
    assert report.failed == 0

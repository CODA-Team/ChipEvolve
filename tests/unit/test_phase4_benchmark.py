from pathlib import Path

from query_agent.benchmark.phase4 import Phase4BenchmarkRunner


def test_phase4_diagnosis_benchmark_is_deterministic(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "benchmarks" / "phase4" / "benchmark.json"
    target = tmp_path / "benchmark.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    report = Phase4BenchmarkRunner().run(tmp_path)
    assert report.total >= 5
    assert report.failed == 0

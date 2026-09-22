from pathlib import Path

from query_agent.benchmark.phase3b import Phase3BBenchmarkRunner


def test_phase3b_analysis_benchmark_is_deterministic(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "benchmarks" / "phase3b" / "benchmark.json"
    target = tmp_path / "benchmark.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    report = Phase3BBenchmarkRunner().run(tmp_path)
    assert report.total >= 5
    assert report.failed == 0

from pathlib import Path

from query_agent.benchmark.phase2 import Phase2BenchmarkRunner


def test_phase2_context_benchmark_is_deterministic(tmp_path: Path) -> None:
    source = Path(__file__).parents[2] / "benchmarks" / "phase2" / "benchmark.json"
    target = tmp_path / "benchmark.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    report = Phase2BenchmarkRunner().run(tmp_path)
    assert report.total >= 8
    assert report.failed == 0
    assert report.metrics["answerability_accuracy"] == 1.0

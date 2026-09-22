import shutil
from pathlib import Path

from query_agent.benchmark import BenchmarkRunner


def test_phase1_benchmark_has_thirty_passing_deterministic_cases(
    tmp_path: Path,
) -> None:
    source = Path(__file__).parents[2] / "benchmarks" / "phase1" / "benchmark.json"
    shutil.copy(source, tmp_path / "benchmark.json")
    report = BenchmarkRunner().run(tmp_path)
    assert report.total >= 30
    assert report.failed == 0
    assert report.metrics["answerability_accuracy"] == 1.0

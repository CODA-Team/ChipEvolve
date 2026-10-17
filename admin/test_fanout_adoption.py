"""Observed electrical violations cannot be hidden by otherwise better PPA."""

import pytest

from admin.test_adoption_consistency import frame_at, validation_for
from admin.test_local_business import deployment
from chip_evolve import selection
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


def test_better_power_with_real_fanout_violations_keeps_legal_incumbent(tmp_path):
    d = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    incumbent = frame_at(tmp_path, "incumbent", 1.0)
    selection.select(
        d, incumbent, "legal branch", validation=validation_for(incumbent, reference)
    )
    pointer = tmp_path / "designs/gcd/incumbent.json"
    original_pointer = digest(pointer)
    candidate = frame_at(tmp_path, "lower-power", 0.9)
    frame = read(candidate)
    frame["metrics"]["finish__timing__drv__max_fanout"] = 4
    write(candidate, frame)
    goal = digest(tmp_path / "objective.json")
    result = digest(candidate)

    actual = selection.select(
        d, candidate, "lower power", validation=validation_for(candidate, reference)
    )

    assert actual["adopted"] is False
    assert actual["failed_conditions"] == ["max_fanout_violations"]
    assert digest(pointer) == original_pointer
    assert digest(candidate) == result
    assert digest(tmp_path / "objective.json") == goal


@pytest.mark.parametrize("count", [0, None])
def test_zero_and_missing_fanout_keep_goal_and_original_facts(tmp_path, count):
    result = frame_at(tmp_path, "candidate", 0.9)
    frame = read(result)
    if count is not None:
        frame["metrics"]["finish__timing__drv__max_fanout"] = count
    goal = digest(tmp_path / "objective.json")
    original = dict(frame["metrics"])

    assert selection.violations(frame) == []
    assert frame["metrics"] == original
    assert digest(tmp_path / "objective.json") == goal
    if count is None:
        assert "finish__timing__drv__max_fanout" not in frame["metrics"]

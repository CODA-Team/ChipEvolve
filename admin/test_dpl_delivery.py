"""Repeated native trial names must preserve the actual checkpoint producer."""

import pytest

from chip_evolve.config import write
from chip_evolve.jobs import digest
from chip_evolve.professional import dpl_producer


def test_same_tag_trials_deliver_the_measured_content(tmp_path):
    placement = tmp_path / "chosen.odb"
    placement.write_bytes(b"first trial")
    original = digest(placement)
    placement.write_bytes(b"second trial measured and selected")
    selected = digest(placement)
    operations = tmp_path / "operations"
    for name, tag, sha, status in [
        ("old", "student", original, "succeeded"),
        ("selected", "student", selected, "succeeded"),
        ("other", "different", selected, "succeeded"),
        ("failed", "student", selected, "failed"),
    ]:
        folder = operations / name
        write(
            folder / "leaf.json",
            {
                "request": {"operation": "baseline", "argv": ["--run-tag", tag]},
                "output_files": {str(placement): sha},
            },
        )
        write(
            folder / "execution.json",
            {
                "run": {
                    "run_id": name,
                    "status": status,
                    "ended_at": "2026-10-15T00:00:00Z",
                }
            },
        )
    assert dpl_producer(operations, placement, "student") == "selected"
    placement.write_bytes(b"unrecorded alteration")
    with pytest.raises(ValueError, match="no successful producer"):
        dpl_producer(operations, placement, "student")

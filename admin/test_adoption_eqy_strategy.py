"""A complete old receipt must not re-authorize the disqualified SAT route."""

import pytest

from admin.test_adoption_consistency import frame_at, validation_for
from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.selection import select


@pytest.mark.parametrize("strategy", [None, "sat", "unqualified"])
def test_adoption_rejects_legacy_eqy_even_with_exact_replay(tmp_path, strategy):
    reference = frame_at(tmp_path, "reference")
    result = frame_at(tmp_path, "candidate", 0.9)
    validation = validation_for(result, reference)
    receipt = read(validation)
    receipt["logic"]["engine"] = "eqy"
    if strategy is not None:
        receipt["logic"]["strategy"] = strategy
    write(validation, receipt)
    original = validation.read_bytes()

    with pytest.raises(ValueError, match="EQY|strategy"):
        select(deployment(tmp_path), result, "new adoption", validation=validation)

    assert validation.read_bytes() == original
    assert not (tmp_path / "designs/gcd/incumbent.json").exists()


def test_adoption_accepts_qualified_eqy_without_changing_historical_receipt(tmp_path):
    reference = frame_at(tmp_path, "reference")
    result = frame_at(tmp_path, "candidate", 0.9)
    validation = validation_for(result, reference)
    receipt = read(validation)
    receipt["logic"].update(engine="eqy", strategy="abc-pdr")
    write(validation, receipt)
    original = validation.read_bytes()

    selected = select(
        deployment(tmp_path), result, "qualified new adoption", validation=validation
    )

    assert selected["adopted"]
    assert validation.read_bytes() == original

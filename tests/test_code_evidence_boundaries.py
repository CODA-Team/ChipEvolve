"""Public evidence readers reject damaged receipts before any additional EDA."""

from pathlib import Path

import pytest
from openroad_platform_client import KernelClient

from chip_evolve.facts import code_evidence
from chip_evolve.core.config import read, write
from chip_evolve.core.contracts import BusinessInputError
from chip_evolve.core.jobs import digest
from tests.test_code_candidate_delivery import inputs, collect


@pytest.mark.parametrize(
    "fault",
    [
        "missing_manifest",
        "manifest_sha",
        "missing_result",
        "result_sha",
        "collection_sha",
        "wrong_summary",
        "wrong_status",
        "wrong_candidate",
        "wrong_header",
    ],
)
def test_completed_inventory_damage_rejects_without_submission_or_rewriting(
    tmp_path, monkeypatch, fault
):
    data = inputs(tmp_path, monkeypatch)
    metadata = collect(data)
    _, _, _, _, _, _, exports, measured = data
    calls = []
    monkeypatch.setattr(
        KernelClient,
        "submit",
        lambda *a, **kw: calls.append(a) or pytest.fail("new EF submit"),
    )
    index_path = Path(metadata["inventory"]["path"])
    index = read(index_path)
    if fault == "missing_manifest":
        index["manifest"]["path"] = str(tmp_path / "missing.json")
    elif fault == "manifest_sha":
        index["manifest"]["sha256"] = "a" * 64
    elif fault in {"missing_result", "result_sha"}:
        completed = next(c for c in index["candidates"] if c["status"] == "completed")
        if fault == "missing_result":
            completed["result"]["path"] = str(tmp_path / "missing-result.json")
        else:
            Path(completed["result"]["path"]).write_text("changed bytes")
    elif fault == "collection_sha":
        index["additional_results"]["sha256"] = "a" * 64
    elif fault in {"wrong_summary", "wrong_header"}:
        path = Path(index["additional_results"]["path"])
        collection = read(path)
        if fault == "wrong_summary":
            collection["candidate_results"][0]["run_id"] = "unrelated"
        else:
            collection["objective_id"] = "a" * 64
        write(path, collection)
        index["additional_results"]["sha256"] = digest(path)
    elif fault == "wrong_status":
        index["candidates"][1]["status"] = "already_delivered"
    else:
        index["candidates"][1]["candidate"]["candidate_id"] = "unrelated"
    write(index_path, index)
    before = index_path.read_bytes()
    delivered, exported = len(measured), len(exports)
    with pytest.raises(BusinessInputError):
        collect(data)
    assert calls == [] and len(measured) == delivered and len(exports) == exported
    assert index_path.read_bytes() == before


def test_completed_summary_does_not_requalify_old_libraries(tmp_path, monkeypatch):
    data = inputs(tmp_path, monkeypatch)
    metadata = collect(data)
    goal = read(data[2]["objective"])
    Path(goal["conditions"]["libraries"][0]["path"]).unlink()
    assert (
        code_evidence.summarize_inventory(Path(metadata["inventory"]["path"])).to_wire()
        == metadata
    )


@pytest.mark.parametrize(
    "fault",
    ["bool_eligible", "wrong_design", "missing_field", "wrong_capability", "duplicate"],
)
def test_export_public_shape_failure_precedes_extra_measurements(
    tmp_path, monkeypatch, fault
):
    data = inputs(tmp_path, monkeypatch)
    submissions = []
    monkeypatch.setattr(
        KernelClient,
        "submit",
        lambda *a, **kw: submissions.append(a) or pytest.fail("new EF submit"),
    )
    exported = data[3]
    if fault == "bool_eligible":
        exported["candidates"][1]["eligible_for_common_measurement"] = "true"
    elif fault == "wrong_design":
        exported["design"] = "other"
    elif fault == "missing_field":
        del exported["candidates"][1]["native_record"]
    elif fault == "wrong_capability":
        exported["capability"] = "eco"
    else:
        exported["candidates"].append(exported["candidates"][1])
    with pytest.raises(BusinessInputError):
        collect(data)
    assert submissions == [] and data[-1] == []

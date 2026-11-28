"""Result decisions reject incomplete numbers and keep their dependency direction."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tests.test_adoption_consistency import frame_at, validation_for
from tests.test_local_business import deployment
from tests.test_local_comparisons import result
from chip_evolve.workflow import comparisons
from chip_evolve.core import selection
from chip_evolve.core.config import read

REQUIRED_FIELDS = (
    "finish__timing__setup__tns",
    "finish__timing__setup__ws",
    "finish__timing__hold__tns",
    "finish__power__total",
    "finish__design__instance__area",
    "finish__design__core__area",
    "finish__design__die__area",
    "finish__timing__drv__max_slew",
    "finish__timing__drv__max_cap",
    "design__violations",
    "route_drc",
)
OPTIONAL_FIELDS = (
    "finish__timing__hold__ws",
    "finish__timing__drv__max_fanout",
)
INVALID_VALUES = (
    pytest.param(float("nan"), "non_finite_metric", id="nan"),
    pytest.param(float("inf"), "non_finite_metric", id="positive-infinity"),
    pytest.param(float("-inf"), "non_finite_metric", id="negative-infinity"),
    pytest.param(None, "missing_metric", id="none"),
    pytest.param("0.0", "invalid_metric", id="numeric-string"),
    pytest.param("failed", "invalid_metric", id="text"),
    pytest.param(True, "invalid_metric", id="boolean"),
    pytest.param({}, "invalid_metric", id="mapping"),
)


def replace_metric(frame, field, value):
    target = frame if field == "route_drc" else frame["metrics"]
    target[field] = value


@pytest.mark.parametrize(
    "field,value,condition",
    [
        ("finish__power__total", 1.01, "power_total_w_max"),
        ("finish__design__instance__area", 10.01, "cell_area_um2_max"),
        ("finish__design__core__area", 20.01, "core_area_um2_max"),
        ("finish__design__die__area", 30.01, "die_area_um2_max"),
        ("finish__timing__setup__tns", -0.01, "setup_tns_ns_min"),
        ("finish__timing__hold__tns", -0.01, "hold_tns_ns_min"),
        ("finish__timing__drv__max_slew", 1, "max_slew_violations"),
        ("finish__timing__drv__max_cap", 1, "max_cap_violations"),
        ("design__violations", 1, "placement_violations"),
        ("route_drc", 1, "route_drc"),
        ("finish__timing__drv__max_fanout", 1, "max_fanout_violations"),
    ],
)
def test_finite_bounds_keep_their_existing_violation_names(
    tmp_path, field, value, condition
):
    frame = result(tmp_path)
    assert selection.violations(frame) == []
    replace_metric(frame, field, value)
    assert selection.violations(frame) == [condition]


@pytest.mark.parametrize("field", (*REQUIRED_FIELDS, *OPTIONAL_FIELDS))
@pytest.mark.parametrize("value,reason", INVALID_VALUES)
def test_invalid_metric_is_an_explicit_violation(tmp_path, field, value, reason):
    frame = result(tmp_path)
    replace_metric(frame, field, value)

    assert f"{reason}:{field}" in selection.violations(frame)
    facts = comparisons.professional_facts(frame)
    assert facts["final_feasible"] is False
    assert facts["final_constraint_violations"] == selection.violations(frame)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_metric_is_an_explicit_violation(tmp_path, field):
    frame = result(tmp_path)
    target = frame if field == "route_drc" else frame["metrics"]
    del target[field]

    assert selection.violations(frame) == [f"missing_metric:{field}"]


@pytest.mark.parametrize("metrics", [None, "failed", []])
def test_missing_or_malformed_metric_container_is_rejected(tmp_path, metrics):
    frame = result(tmp_path)
    frame["metrics"] = metrics
    assert selection.violations(frame)
    with pytest.raises(ValueError, match="metrics"):
        comparisons.compare(result(tmp_path), frame)


@pytest.mark.parametrize("side", ["reference", "candidate"])
@pytest.mark.parametrize("value,reason", INVALID_VALUES)
def test_comparison_rejects_invalid_values_before_computing_deltas(
    tmp_path, side, value, reason
):
    reference = result(tmp_path)
    candidate = deepcopy(reference)
    frame = reference if side == "reference" else candidate
    replace_metric(frame, "finish__power__total", value)

    with pytest.raises(ValueError, match=side + ".*" + reason):
        comparisons.compare(reference, candidate)


@pytest.mark.parametrize("with_incumbent", [False, True])
@pytest.mark.parametrize("field", (*REQUIRED_FIELDS, *OPTIONAL_FIELDS))
@pytest.mark.parametrize("value,reason", INVALID_VALUES)
def test_invalid_result_never_replaces_a_finite_incumbent_or_becomes_selected(
    tmp_path, with_incumbent, field, value, reason
):
    config = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    pointer = tmp_path / "designs/gcd/incumbent.json"
    previous = None
    if with_incumbent:
        selected = selection.select(
            config,
            reference,
            "finite reference",
            validation=validation_for(reference, reference),
        )
        assert selected["adopted"]
        previous = pointer.read_bytes()
    candidate = frame_at(tmp_path, "candidate", 0.8)
    frame = read(candidate)
    replace_metric(frame, field, value)
    # Legacy or external JSON can contain NaN tokens that config.write rejects.
    candidate.write_text(json.dumps(frame))
    original = candidate.read_bytes()
    validation = validation_for(candidate, reference)

    receipt = selection.select(
        config, candidate, "must reject invalid facts", validation=validation
    )

    assert receipt["adopted"] is False
    assert f"{reason}:{field}" in receipt["failed_conditions"]
    assert candidate.read_bytes() == original
    assert read(Path(receipt["decision"])) == receipt
    if with_incumbent:
        assert pointer.read_bytes() == previous
    else:
        assert not pointer.exists()


def test_finite_historical_comparison_and_adoption_order_stay_compatible(tmp_path):
    config = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    better = frame_at(tmp_path, "better", 0.8)
    worse = frame_at(tmp_path, "worse", 0.9)
    receipt = comparisons.compare(read(reference), read(better))
    assert receipt["constraint_violations"] == []
    assert receipt["deltas"]["finish__power__total"] == {
        "reference": 1.0,
        "candidate": 0.8,
        "delta": 0.8 - 1.0,
        "percent": 100 * (0.8 - 1.0),
    }
    assert all(
        row["delta"] == 0
        for key, row in receipt["deltas"].items()
        if key != "finish__power__total"
    )
    assert selection.select(
        config, worse, "first feasible", validation=validation_for(worse, reference)
    )["adopted"]
    assert selection.select(
        config, better, "lower power", validation=validation_for(better, reference)
    )["adopted"]
    rejected = selection.select(
        config, worse, "dominated", validation=validation_for(worse, reference)
    )
    assert rejected["failed_conditions"] == ["dominated_incumbent"]
    assert read(tmp_path / "designs/gcd/incumbent.json")["run_id"] == "better"


def root_import_graph(package=None):
    from tests.root_architecture import implementation_graph

    if package is None:
        package = Path(__file__).resolve().parents[1] / "chip_evolve"
    graph = implementation_graph(package)
    # Keep the original gate's semantic owner names, after recursive resolution.
    assert len({name.split(".")[-1] for name in graph}) == len(graph)
    return {
        name.split(".")[-1]: {t.split(".")[-1] for t in targets}
        for name, targets in graph.items()
    }


def reachable_modules(graph, start):
    reached = set()
    pending = list(graph[start])
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        pending.extend(graph[name])
    return reached


def test_comparison_and_selection_leave_all_import_cycles_including_local_imports():
    graph = root_import_graph()
    assert graph["metrics"] == set()
    assert graph["proof_policy"] == set()
    assert "selection" in reachable_modules(graph, "comparisons")
    assert "comparisons" not in reachable_modules(graph, "selection")
    for name in ("selection", "comparisons"):
        assert name not in reachable_modules(graph, name)

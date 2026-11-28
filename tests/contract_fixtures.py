"""Explicit specialist requests for isolated native transport tests."""

from chip_evolve.contracts import SearchBudget, SpecialistRequest


def specialist_request(
    capability,
    *,
    design="gcd",
    key="test",
    seconds=60,
    rounds=1,
    candidates=None,
    operation="evolve",
    flow_recipe="legacy",
    code_source=None,
):
    if candidates is None:
        candidates = {"flow": 12, "dpl": 3, "goal": 4}.get(capability)
    return SpecialistRequest(
        design,
        key,
        capability,
        operation,
        SearchBudget(seconds, rounds, candidates),
        code_source,
        flow_recipe,
    )

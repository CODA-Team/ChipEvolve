"""Explicit specialist requests for isolated native transport tests."""

from chip_evolve.core.contracts import SearchBudget, SpecialistRequest


def unit_admission(monkeypatch, *, orchestration=False):
    """Explicit capacity collaborator for legacy offline transport/unit fixtures.

    These fixtures intentionally have no image, installed consumer or EF service.
    Keep their existing behavior assertions; real profile/admission behavior is
    exercised separately by test_runtime_profile and test_resource_admission.
    """
    from chip_evolve.workflow import commands
    from chip_evolve.core import jobs, resources
    from chip_evolve.core.toolchain import file_ref, PROFILE_DIRECTORY

    capacity = resources.CapacitySnapshot(
        "http://offline-unit",
        256,
        1024 << 30,
        "public_resources",
        None,
        "synthetic-unit",
    )

    def admit(deployment, client, budget):
        resources.require_capacity(budget, capacity)
        return capacity

    monkeypatch.setattr(jobs, "admit_task", admit)
    if orchestration:
        from chip_evolve.workflow import flow, dpl, goal, eco

        for adapter in (flow, dpl, goal, eco):
            monkeypatch.setattr(adapter, "ensure_specialist_plan", lambda *a: None)

        def plan(deployment, design, budgets, client=None):
            for budget in budgets:
                resources.require_capacity(budget, capacity)
            return resources.ExecutionPlan(
                file_ref(deployment.path),
                file_ref(PROFILE_DIRECTORY / "resources-v1.json"),
                budgets,
                capacity,
            )

        monkeypatch.setattr(commands, "plan_execution", plan)
        monkeypatch.setattr(
            commands,
            "specialist_budgets",
            lambda *a: (resources.resolve_budget("legacy-api"),),
        )
        monkeypatch.setattr(resources, "ensure_specialist_plan", lambda *a: None)


def unit_native_admission(deployment, request, profile, *, threads=None):
    """Verify actual frozen native limits against an explicit synthetic service."""
    from chip_evolve.core import resources

    capacity = resources.CapacitySnapshot(
        "http://offline-unit",
        256,
        1024 << 30,
        "public_resources",
        None,
        "synthetic-unit",
    )
    for budget in resources.native_budgets(
        request.capability,
        profile,
        request.seconds,
        operation=request.operation,
        code_source=request.code_source is not None,
        threads=threads,
    ):
        resources.require_capacity(budget, capacity)


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

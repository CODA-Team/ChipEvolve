"""Canonical stage semantics shared by context policies."""

from query_agent.domain.experiment import (
    ExperimentRun,
    ExperimentStage,
    canonical_stage_key,
)


def select_stage(run: ExperimentRun, requested: str | None) -> ExperimentStage | None:
    """Select one stage by canonical key, preserving the provider's spelling."""

    if requested is None:
        return None
    wanted = canonical_stage_key(requested)
    return next((stage for stage in run.stages if stage.canonical_key == wanted), None)


def stage_satisfies(run: ExperimentRun, requested: str | None) -> bool:
    """Whether a run has a successful requested stage."""

    if requested is None:
        return True
    stage = select_stage(run, requested)
    return stage is not None and stage.status.value == "succeeded"

"""Deterministic run selection policies."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from query_agent.domain.experiment import (
    CandidateRejection,
    ContextSelection,
    ExperimentRun,
    ExperimentStatus,
    canonical_stage_key,
)
from query_agent.domain.query import RunSelectionMode

from .stage_selection import stage_satisfies


class RunSelectionPolicy:
    """Select runs using explicit lifecycle and stage rules."""

    def select(
        self,
        runs: Sequence[ExperimentRun],
        *,
        mode: RunSelectionMode,
        requested_stage: str | None = None,
        explicit_run_id: str | None = None,
    ) -> tuple[tuple[ExperimentRun, ...], ContextSelection]:
        effective_mode = (
            RunSelectionMode.EXPLICIT
            if mode is RunSelectionMode.AUTO and explicit_run_id
            else mode
        )
        ordered = tuple(sorted(runs, key=_run_time, reverse=True))
        rejected: list[CandidateRejection] = []
        selected: list[ExperimentRun] = []
        if effective_mode is RunSelectionMode.EXPLICIT:
            selected = [run for run in ordered if run.run_id == explicit_run_id]
            if not selected:
                rejected.append(
                    CandidateRejection(
                        candidate_id=explicit_run_id or "unknown",
                        reason_code="EXPLICIT_RUN_NOT_FOUND",
                        detail="the requested run is not available from the provider",
                    )
                )
        elif effective_mode is RunSelectionMode.CURRENT:
            if ordered:
                newest = ordered[0]
                if newest.status is ExperimentStatus.SUCCEEDED:
                    selected = [newest]
                else:
                    rejected.append(
                        CandidateRejection(
                            candidate_id=newest.run_id,
                            reason_code="CURRENT_RUN_NOT_COMPLETE",
                            detail=(
                                "the newest run is not completed; an older run "
                                "cannot satisfy a current-state request"
                            ),
                        )
                    )
        elif effective_mode is RunSelectionMode.LATEST:
            selected = list(ordered[:1])
        else:
            for run in ordered:
                if not run.status.valid:
                    rejected.append(
                        CandidateRejection(
                            candidate_id=run.run_id,
                            reason_code="RUN_NOT_VALID",
                            detail=f"run status is {run.status.value}",
                        )
                    )
                    continue
                if not stage_satisfies(run, requested_stage):
                    rejected.append(
                        CandidateRejection(
                            candidate_id=run.run_id,
                            reason_code="STAGE_NOT_COMPLETE",
                            detail="requested stage is absent or not successful",
                        )
                    )
                    continue
                selected.append(run)
                if effective_mode is not RunSelectionMode.COMPARISON:
                    break
        if (
            requested_stage
            and selected
            and effective_mode
            in {
                RunSelectionMode.CURRENT,
                RunSelectionMode.LATEST,
                RunSelectionMode.EXPLICIT,
            }
        ):
            run = selected[0]
            if not stage_satisfies(run, requested_stage):
                rejected.append(
                    CandidateRejection(
                        candidate_id=run.run_id,
                        reason_code="STAGE_NOT_COMPLETE",
                        detail="requested stage is absent or not successful",
                    )
                )
                selected = []
        reason_codes = _reason_codes(effective_mode, selected, rejected)
        selection = ContextSelection(
            selected_run_id=selected[0].run_id if selected else None,
            selected_stage_key=(
                canonical_stage_key(requested_stage)
                if selected and requested_stage
                else None
            ),
            candidate_run_ids=tuple(run.run_id for run in ordered),
            rejected=tuple(rejected),
            reason_codes=reason_codes,
        )
        return tuple(selected), selection


def _run_time(run: ExperimentRun) -> datetime:
    return run.created_at or run.completed_at or datetime.min.replace(tzinfo=UTC)


def _reason_codes(
    mode: RunSelectionMode,
    selected: Sequence[ExperimentRun],
    rejected: Sequence[CandidateRejection],
) -> tuple[str, ...]:
    reasons = [f"POLICY_{mode.value}"]
    if selected:
        reasons.append("RUN_SELECTED")
    else:
        reasons.append("NO_ELIGIBLE_RUN")
    reasons.extend(item.reason_code for item in rejected)
    return tuple(dict.fromkeys(reasons))

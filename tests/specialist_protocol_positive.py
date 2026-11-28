"""Static callers bind the actual public implementations to one protocol."""

from pathlib import Path

from openroad_platform_client import KernelClient

from chip_evolve.config import Deployment
from chip_evolve.contracts import (
    CandidateCollection,
    CandidateDeliverySummary,
    CodeCapability,
    NativeCandidateExport,
    ObjectiveRef,
    SpecialistAdapter,
    SpecialistReply,
    VerifiedNativeProducer,
)
from chip_evolve.command_requests import NormalizedRunCommand
from chip_evolve.code_evidence import (
    export_candidates,
    summarize_inventory,
    verify_candidate_producer,
)
from chip_evolve.flow_delivery import collect_completed, collect_failed_evidence
from chip_evolve.professional import (
    PreparedSpecialist,
    SpecialistPreflight,
    inspect_inputs,
    prepare_inputs,
    dispatch_prepared,
)
from chip_evolve.dpl import run_dpl
from chip_evolve.flow import run_flow
from chip_evolve.eco import run_eco
from chip_evolve.goal import run_goal

flow: SpecialistAdapter = run_flow
dpl: SpecialistAdapter = run_dpl
goal: SpecialistAdapter = run_goal
eco: SpecialistAdapter = run_eco


def code_delivery(
    deployment: Deployment,
    experiment: Path,
    capability: CodeCapability,
    output: Path,
    client: KernelClient,
) -> tuple[NativeCandidateExport, VerifiedNativeProducer, CandidateDeliverySummary]:
    batch = export_candidates(deployment, experiment, capability, output)
    producer = verify_candidate_producer(
        client, batch.binding, batch.candidates[0], output.parent
    )
    summary = summarize_inventory(output.parent / "inventory.json")
    return batch, producer, summary


def flow_delivery(
    deployment: Deployment, experiment: Path, objective: ObjectiveRef
) -> tuple[CandidateCollection, CandidateCollection]:
    completed = collect_completed(deployment, "gcd", experiment, objective)
    evidence = collect_failed_evidence(deployment, "gcd", experiment, objective)
    return completed, evidence


def staged_dispatch(
    deployment: Deployment, command: NormalizedRunCommand, experiment: Path
) -> SpecialistReply:
    preflight: SpecialistPreflight = inspect_inputs(deployment, command)
    prepared: PreparedSpecialist = prepare_inputs(deployment, preflight, experiment)
    return dispatch_prepared(deployment, prepared, experiment)

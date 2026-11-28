"""Expected Pyright diagnostics, intentionally excluded from runtime pytest."""

from pathlib import Path
from chip_evolve.config import Deployment
from chip_evolve.contracts import (
    DiagnosisContextRef,
    MeasuredResult,
    ObjectiveRef,
    PhysicalResult,
    SpecialistAdapter,
    SpecialistReply,
    SpecialistRequest,
)
from chip_evolve.flow import run_flow
from chip_evolve.code_evidence import export_candidates, verify_candidate_producer
from chip_evolve.flow_delivery import collect_completed
from chip_evolve.professional import PreparedSpecialist, dispatch_prepared
from chip_evolve.contracts import NativeCampaignBinding
from openroad_platform_client import KernelClient


def wrong_source(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: MeasuredResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> SpecialistReply:
    return run_flow(deployment, request, experiment, source, objective, context)


def wrong_reply(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> dict[str, str]:
    return {"run_id": source.run_id}


bad_adapter: SpecialistAdapter = wrong_reply
bad_result: PhysicalResult = {"run_id": "untyped"}


def wrong_code_capability(deployment: Deployment, experiment: Path) -> None:
    export_candidates(deployment, experiment, "eco", experiment / "export.json")


def wrong_candidate(
    client: KernelClient, binding: NativeCampaignBinding, output: Path
) -> None:
    verify_candidate_producer(client, binding, {"candidate_id": "untyped"}, output)


def wrong_prepared(deployment: Deployment, experiment: Path) -> SpecialistReply:
    prepared: PreparedSpecialist = {"request": "untyped"}
    return dispatch_prepared(deployment, prepared, experiment)


def wrong_flow_reply(
    deployment: Deployment, experiment: Path, objective: ObjectiveRef
) -> SpecialistReply:
    return collect_completed(deployment, "gcd", experiment, objective)

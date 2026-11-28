"""Named task budgets and evidence-based capacity checks; EF owns scheduling."""

from __future__ import annotations

import math
import hashlib
import json
from collections.abc import Sequence, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from openroad_platform_contracts import ResourceRequest, TaskSpec
from openroad_platform_client import KernelClient

from chip_evolve.core.config import Deployment, write
from chip_evolve.core.contracts import (
    BusinessInputError,
    FileRef,
    SpecialistRequest,
    SpecialistKind,
    Operation,
)
from chip_evolve.core.toolchain import (
    PROFILE_DIRECTORY,
    file_ref,
    profile_document,
    profile_object,
    profile_text,
    profile_records,
    parse_ref,
    load_runtime_profile,
    ref_payload,
    check_ref,
    installed_identity,
)


EF_DISTRIBUTIONS = tuple(
    "openroad-platform-" + name
    for name in (
        "contracts",
        "client",
        "runtime",
        "registry",
        "evaluator",
        "provenance",
        "gateway",
    )
)


@dataclass(frozen=True)
class TaskBudget:
    kind: str
    limits: ResourceRequest
    timeout_seconds: int
    native_threads: int
    source_ref: FileRef


@dataclass(frozen=True)
class CapacitySnapshot:
    kernel_url: str
    budget_cpu_cores: int
    budget_memory_bytes: int
    source: str
    origin: FileRef | None
    service_identity: str


@dataclass(frozen=True)
class ExecutionPlan:
    profile_ref: FileRef
    policy_ref: FileRef
    budgets: tuple[TaskBudget, ...]
    capacity: CapacitySnapshot


def positive(value: Any, field: str, *, integer: bool = True) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
        or value <= 0
    ):
        raise BusinessInputError(
            "invalid_resource", field, "positive finite number required"
        )
    if integer and not isinstance(value, int):
        raise BusinessInputError("invalid_resource", field, "integer required")
    return value


def preset(kind: str) -> dict[str, int]:
    value = profile_document(PROFILE_DIRECTORY / "resources-v1.json")
    if value.get("schema_version") != "chip-evolve.resources.v1" or not isinstance(
        value.get("presets"), dict
    ):
        raise BusinessInputError(
            "unsupported_resource_schema", "resources", "expected v1"
        )
    presets = profile_object(value["presets"], "presets")
    if kind not in presets:
        raise BusinessInputError(
            "unknown_resource_kind", kind, "named task family required"
        )
    fields = profile_object(presets[kind], "presets." + kind)
    required = {"cpu_cores", "memory_gib", "processes", "seconds", "threads"}
    if not required <= set(fields) or set(fields) - required - {"lto_workers"}:
        raise BusinessInputError(
            "invalid_resource",
            kind,
            "explicit CPU/memory/process/time/thread fields required",
        )
    return {key: int(positive(item, kind + "." + key)) for key, item in fields.items()}


def resolve_budget(
    kind: str,
    *,
    cpu: int | None = None,
    memory_gib: int | None = None,
    processes: int | None = None,
    seconds: int | None = None,
    threads: int | None = None,
) -> TaskBudget:
    defaults = preset(kind)
    cores = int(positive(defaults["cpu_cores"] if cpu is None else cpu, "cpu_cores"))
    memory = int(
        positive(
            defaults["memory_gib"] if memory_gib is None else memory_gib, "memory_gib"
        )
    )
    count = int(
        positive(defaults["processes"] if processes is None else processes, "processes")
    )
    timeout = int(
        positive(defaults["seconds"] if seconds is None else seconds, "timeout_seconds")
    )
    workers = int(positive(cores if threads is None else threads, "native_threads"))
    if (
        kind in {"code-build", "code-variant"}
        and memory < preset("code-build")["memory_gib"]
    ):
        raise BusinessInputError(
            "unqualified_build_budget",
            kind,
            "full LTO requires at least 64 GiB; no qualified smaller build family supplied",
        )
    if kind in {"code-build", "code-variant"} and (
        cores < preset("code-build")["cpu_cores"]
        or count < preset("code-build")["processes"]
    ):
        raise BusinessInputError(
            "unqualified_build_budget",
            kind,
            "full build requires 8 CPU / 2048 processes",
        )
    if workers > cores:
        raise BusinessInputError(
            "resource_threads_exceed_reservation",
            kind,
            "native threads exceed CPU reservation",
        )
    limits = ResourceRequest(
        cpu_cores=cores, memory_bytes=memory << 30, processes=count
    )
    limits.validate()
    return TaskBudget(
        kind,
        limits,
        timeout,
        workers,
        file_ref(PROFILE_DIRECTORY / "resources-v1.json"),
    )


def require_capacity(budget: TaskBudget, capacity: CapacitySnapshot) -> None:
    positive(capacity.budget_cpu_cores, "capacity.cpu_cores")
    positive(capacity.budget_memory_bytes, "capacity.memory_bytes")
    budget.limits.validate()
    if budget.limits.cpu_seconds is not None:
        positive(budget.limits.cpu_seconds, "cpu_seconds", integer=False)
    if budget.limits.cpu_cores is None or budget.limits.memory_bytes is None:
        raise BusinessInputError(
            "unbounded_resource", budget.kind, "explicit CPU and memory required"
        )
    if (
        budget.limits.cpu_cores > capacity.budget_cpu_cores
        or budget.limits.memory_bytes > capacity.budget_memory_bytes
    ):
        raise BusinessInputError(
            "capacity_exceeded",
            budget.kind,
            f"requires {budget.limits.describe()}; instance budget is {capacity.budget_cpu_cores} CPU / {capacity.budget_memory_bytes} bytes",
        )


def process_identity(pid: int) -> tuple[str, list[str]]:
    positive(pid, "pid")
    stat = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
    if stat[0] == "Z":
        raise BusinessInputError(
            "capacity_unverified", "pid", "recorded process is a zombie"
        )
    command = [
        item.decode()
        for item in Path("/proc", str(pid), "cmdline").read_bytes().split(b"\0")
        if item
    ]
    return stat[19], command


def command_capacity(command: list[str]) -> tuple[int, int]:
    if "openroad_platform_gateway" not in command or "-m" not in command:
        raise BusinessInputError(
            "capacity_unverified", "command", "owned EF gateway required"
        )

    module_index = command.index("-m")
    if (
        module_index + 1 >= len(command)
        or command[module_index + 1] != "openroad_platform_gateway"
        or any(arg not in {"-I", "-E", "-s", "-u"} for arg in command[1:module_index])
    ):
        raise BusinessInputError(
            "capacity_unverified", "command", "fixed gateway module entry required"
        )

    def argument(flag: str) -> str:
        if command.count(flag) != 1:
            raise BusinessInputError(
                "capacity_unverified", flag, "one explicit argument required"
            )
        index = command.index(flag)
        if index + 1 >= len(command):
            raise BusinessInputError("capacity_unverified", flag, "value missing")
        return command[index + 1]

    if argument("--platform-fraction") != "1.0":
        raise BusinessInputError(
            "capacity_unverified",
            "platform_fraction",
            "empty local startup requires explicit 1.0; use public resources otherwise",
        )
    return int(
        positive(int(argument("--capacity-cpu-cores")), "capacity.cpu_cores")
    ), int(positive(int(argument("--capacity-memory-bytes")), "capacity.memory_bytes"))


def worker_is_owned(pid: int, owner: int) -> bool:
    """Check the reported worker's ancestry; never discover/adopt other services."""
    for _ in range(32):
        if pid == owner:
            return True
        if pid <= 1:
            return False
        try:
            stat = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            return False
        pid = int(stat[1])
    return False


def startup_receipt(
    workspace: Path,
    config: dict[str, Any],
    record: dict[str, Any],
    health: dict[str, Any],
) -> FileRef:
    birth, command = process_identity(record["pid"])
    if birth != record["birth"] or command != record["command"]:
        raise BusinessInputError(
            "capacity_unverified", "process", "PID/birth/command differs"
        )
    cpu, memory = command_capacity(command)
    if cpu != config["cpu_cores"] or memory != config["memory_gib"] << 30:
        raise BusinessInputError(
            "capacity_unverified", "configuration", "actual startup capacity differs"
        )
    workers = profile_records(health.get("workers"), "health.workers")
    if health.get("service") != "kernel" or health.get("status") != "ok" or not workers:
        raise BusinessInputError(
            "capacity_unverified", "health", "live EF workers required"
        )
    if not all(
        worker_is_owned(int(positive(worker.get("pid"), "worker.pid")), record["pid"])
        for worker in workers
    ):
        raise BusinessInputError(
            "capacity_unverified",
            "health.workers",
            "worker is outside the owned gateway tree",
        )
    identities = [
        installed_identity(Path(command[0]), name) for name in EF_DISTRIBUTIONS
    ]
    target = Path(config["state_root"]) / "capacity-receipt.json"
    value = {
        "schema_version": "chip-evolve.capacity.v1",
        "source": "owned_startup",
        "kernel_url": "http://127.0.0.1:" + str(config["kernel_port"]),
        "process": record,
        "budget_cpu_cores": cpu,
        "budget_memory_bytes": memory,
        "instance_root": config["state_root"],
        "state_root": str(Path(config["state_root"]) / "execution"),
        "gateway": {"distributions": identities},
        "worker_ids": [
            profile_text(worker.get("worker_id"), "health.worker_id")
            for worker in workers
        ],
    }
    write(target, value)
    return file_ref(target)


def owned_capacity(
    deployment: Deployment, health: dict[str, Any]
) -> CapacitySnapshot | None:
    location = deployment.value.get("capacity_receipt")
    if location is None:
        return None
    url = profile_text(deployment.value["kernel_url"], "kernel_url")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise BusinessInputError(
            "capacity_unverified",
            "kernel_url",
            "startup evidence applies only to the local host",
        )
    origin = file_ref(Path(location))
    value = profile_document(origin.path)
    if (
        value.get("schema_version") != "chip-evolve.capacity.v1"
        or value.get("kernel_url") != url
    ):
        raise BusinessInputError(
            "capacity_unverified", "startup", "schema or URL differs"
        )
    process = profile_object(value.get("process"), "startup.process")
    pid = int(positive(process.get("pid"), "pid"))
    birth, command = process_identity(pid)
    if birth != process.get("birth") or command != process.get("command"):
        raise BusinessInputError(
            "capacity_unverified", "startup.process", "stale PID/birth/command"
        )
    cpu, memory = command_capacity(command)
    if (
        value.get("budget_cpu_cores") != cpu
        or value.get("budget_memory_bytes") != memory
    ):
        raise BusinessInputError(
            "capacity_unverified",
            "startup.capacity",
            "declared capacity differs from actual argv",
        )
    if str(deployment.state) != value.get("instance_root"):
        raise BusinessInputError(
            "capacity_unverified", "startup.instance", "business instance differs"
        )
    port = urlsplit(url).port
    if (
        any(
            command.count(flag) != 1 or command.index(flag) + 1 >= len(command)
            for flag in ["--port", "--state-root"]
        )
        or command[command.index("--port") + 1] != str(port)
        or command[command.index("--state-root") + 1] != value.get("state_root")
    ):
        raise BusinessInputError(
            "capacity_unverified", "startup.instance", "port or state root differs"
        )
    gateway = profile_object(value.get("gateway"), "startup.gateway")
    identities = profile_records(
        gateway.get("distributions"), "startup.gateway.distributions"
    )
    if {
        profile_text(item.get("distribution"), "distribution") for item in identities
    } != set(EF_DISTRIBUTIONS):
        raise BusinessInputError(
            "capacity_unverified",
            "startup.gateway",
            "all seven installed component identities required",
        )
    for identity in identities:
        for reference in profile_records(
            identity.get("files"), "startup.gateway.files"
        ):
            parse_ref(reference, "startup.gateway.files")
    workers = profile_records(health.get("workers"), "health.workers")
    if not all(
        worker_is_owned(int(positive(worker.get("pid"), "worker.pid")), pid)
        for worker in workers
    ):
        raise BusinessInputError(
            "capacity_unverified",
            "health.workers",
            "worker is outside the owned gateway tree",
        )
    live_ids = {
        profile_text(worker.get("worker_id"), "health.worker_id")
        for worker in workers
        if worker.get("state") != "stale"
    }
    expected = value.get("worker_ids")
    if (
        not isinstance(expected, list)
        or not expected
        or not live_ids
        or not all(
            profile_text(item, "startup.worker_ids") in live_ids
            for item in cast(Sequence[object], expected)
        )
    ):
        raise BusinessInputError(
            "capacity_unverified",
            "health.workers",
            "owned worker identities changed or stale",
        )
    return CapacitySnapshot(
        url, cpu, memory, "owned_startup", origin, birth + ":" + str(pid)
    )


def read_capacity(deployment: Deployment, client: KernelClient) -> CapacitySnapshot:
    health = client.health()
    if health.get("service") != "kernel" or health.get("status") != "ok":
        raise BusinessInputError("capacity_unverified", "health", "healthy EF required")
    local = owned_capacity(deployment, health)
    workers = profile_records(health.get("workers"), "health.workers")
    public_identity = hashlib.sha256(
        json.dumps(
            sorted(
                (
                    profile_text(worker.get("worker_id"), "worker_id"),
                    int(positive(worker.get("pid", 1), "worker.pid")),
                )
                for worker in workers
                if worker.get("state") != "stale"
            )
        ).encode()
    ).hexdigest()
    rows = client.runs(limit=1)
    if rows:
        resource = client.resources(rows[0]["run_id"])
        if resource.get("run") != rows[0]["run_id"]:
            raise BusinessInputError(
                "capacity_unverified", "resources.run", "run identity differs"
            )
        capacity = profile_object(resource.get("capacity"), "resources.capacity")
        cpu = int(positive(capacity.get("budget_cpu_cores"), "capacity.cpu_cores"))
        memory = int(
            positive(capacity.get("budget_memory_bytes"), "capacity.memory_bytes")
        )
        if local and (cpu, memory) != (
            local.budget_cpu_cores,
            local.budget_memory_bytes,
        ):
            raise BusinessInputError(
                "capacity_unverified",
                "capacity",
                "public resources and owned startup disagree",
            )
        return CapacitySnapshot(
            deployment.value["kernel_url"],
            cpu,
            memory,
            "public_resources",
            local.origin if local else None,
            local.service_identity if local else public_identity,
        )
    if local:
        return local
    raise BusinessInputError(
        "capacity_unverified",
        "capacity",
        "empty remote has no public resource record or verifiable owned startup; no probe job was submitted",
    )


def admit_task(
    deployment: Deployment, client: KernelClient, budget: TaskBudget
) -> CapacitySnapshot:
    load_runtime_profile(deployment)
    check_ref(budget.source_ref)
    capacity = read_capacity(deployment, client)
    require_capacity(budget, capacity)
    return capacity


def frozen_budget(
    path: Path, *, cpu: int | None, memory_gib: int | None, seconds: int | None
) -> TaskBudget:
    """Saved TaskSpec values outrank current defaults; never rewrite their bytes."""
    task = TaskSpec.from_dict(profile_document(path))
    if (
        task.resources is None
        or task.resources.cpu_cores is None
        or task.resources.memory_bytes is None
    ):
        raise BusinessInputError(
            "unbounded_resource", str(path), "saved explicit resource limits required"
        )
    limits = task.resources.to_dict()
    if cpu is not None:
        limits["cpu_cores"] = int(positive(cpu, "cpu_cores"))
    if memory_gib is not None:
        limits["memory_bytes"] = int(positive(memory_gib, "memory_gib")) << 30
    selected = budget_from_limits(
        "saved-task",
        limits,
        int(
            positive(
                task.timeout_seconds if seconds is None else seconds, "timeout_seconds"
            )
        ),
    )
    return TaskBudget(
        selected.kind,
        selected.limits,
        selected.timeout_seconds,
        selected.native_threads,
        file_ref(path),
    )


def plan_execution(
    deployment: Deployment,
    design_id: str,
    budgets: tuple[TaskBudget, ...],
    client: KernelClient | None = None,
) -> ExecutionPlan:
    profile = load_runtime_profile(deployment)
    kernel = (
        client
        if client is not None
        else KernelClient(deployment.value["kernel_url"], timeout=60)
    )
    capacity = read_capacity(deployment, kernel)
    for budget in budgets:
        check_ref(budget.source_ref)
        require_capacity(budget, capacity)
    return ExecutionPlan(profile.origin, profile.policy, budgets, capacity)


def bind_execution_plan(plan: ExecutionPlan, experiment: Path) -> None:
    check_ref(plan.profile_ref)
    check_ref(plan.policy_ref)
    value = {
        "schema_version": "chip-evolve.execution-plan.v1",
        "profile": ref_payload(plan.profile_ref),
        "policy": ref_payload(plan.policy_ref),
        "budgets": [
            {
                "kind": budget.kind,
                "limits": budget.limits.to_dict(),
                "timeout_seconds": budget.timeout_seconds,
                "native_threads": budget.native_threads,
            }
            for budget in plan.budgets
        ],
        "capacity": {
            "kernel_url": plan.capacity.kernel_url,
            "source": plan.capacity.source,
            "cpu_cores": plan.capacity.budget_cpu_cores,
            "memory_bytes": plan.capacity.budget_memory_bytes,
            "service_identity": plan.capacity.service_identity,
        },
    }
    path = experiment / "execution-plan.json"
    if path.exists():
        if profile_document(path) != value:
            raise BusinessInputError(
                "execution_plan_changed", str(path), "frozen plan differs"
            )
        return
    write(path, value)


def orfs_budget(deployment: Deployment, design_id: str, seconds: int) -> TaskBudget:
    configured = deployment.design(design_id).get("orfs_execution", {})
    defaults = preset("orfs")
    return resolve_budget(
        "orfs",
        cpu=int(
            positive(
                configured.get("cpu_cores", defaults["cpu_cores"]), "orfs.cpu_cores"
            )
        ),
        memory_gib=int(
            positive(
                configured.get("memory_gib", defaults["memory_gib"]), "orfs.memory_gib"
            )
        ),
        seconds=seconds,
    )


def budget_from_limits(
    kind: str, value: dict[str, Any], seconds: int, *, threads: int | None = None
) -> TaskBudget:
    limits = ResourceRequest.from_dict(value)
    if (
        limits.cpu_cores is None
        or limits.memory_bytes is None
        or limits.processes is None
    ):
        raise BusinessInputError(
            "unbounded_resource", kind, "CPU, memory and process threshold required"
        )
    effective = (
        max(limits.cpu_cores, int(positive(threads, "threads")))
        if threads is not None
        else limits.cpu_cores
    )
    memory = limits.memory_bytes
    process_count = limits.processes
    limits = ResourceRequest(
        cpu_seconds=limits.cpu_seconds,
        cpu_cores=effective,
        memory_bytes=memory,
        processes=process_count,
    )
    if limits.cpu_seconds is not None:
        positive(limits.cpu_seconds, "cpu_seconds", integer=False)
    if kind in {"code-build", "code-variant"} and (
        memory < preset("code-build")["memory_gib"] << 30
        or effective < preset("code-build")["cpu_cores"]
        or process_count < preset("code-build")["processes"]
    ):
        raise BusinessInputError(
            "unqualified_build_budget",
            kind,
            "full LTO budget requires 64 GiB / 8 CPU / 2048 processes; smaller variants need separately qualified evidence",
        )
    return TaskBudget(
        kind,
        limits,
        int(positive(seconds, "timeout_seconds")),
        int(positive(threads, "native_threads")) if threads is not None else effective,
        file_ref(PROFILE_DIRECTORY / "resources-v1.json"),
    )


def native_budgets(
    capability: SpecialistKind,
    profile: dict[str, Any],
    seconds: int,
    *,
    operation: Operation = "evolve",
    code_source: bool = False,
    threads: int | Mapping[str, int] | None = None,
) -> tuple[TaskBudget, ...]:
    if capability == "flow":
        cores = int(positive(profile.get("threads"), "flow.threads"))
        base = {"cpu_cores": cores, **profile["resources"]}
        stages = [
            base,
            *[
                {**base, **value}
                for value in profile.get("stage_resources", {}).values()
            ],
        ]
        return tuple(
            budget_from_limits(
                "flow-stage", value, profile["stage_timeout_seconds"], threads=cores
            )
            for value in stages
        )
    if capability == "eco":
        return (
            resolve_budget(
                "eco-session",
                cpu=int(positive(profile.get("cpu_cores"), "eco.cpu_cores")),
                memory_gib=int(positive(profile.get("memory_gib"), "eco.memory_gib")),
                seconds=int(
                    positive(profile.get("timeout_seconds"), "eco.timeout_seconds")
                ),
            ),
        )
    configured = profile["resources"]
    active = ["physical"]
    if capability == "goal":
        active.append("analysis")
    if operation != "replay" or code_source:
        active.extend(["build", "variant_build"])
    result: list[TaskBudget] = []
    families = {
        "build": "code-build",
        "variant_build": "code-variant",
        "physical": "code-physical",
        "analysis": "code-analysis",
    }
    for name in active:
        if name in configured:
            limits = configured[name]
        elif name == "variant_build":
            limits = configured["build"]
        else:
            limits = resolve_budget(families[name]).limits.to_dict()
        result.append(
            budget_from_limits(
                families[name],
                limits,
                seconds,
                threads=(threads.get(name) if isinstance(threads, Mapping) else threads)
                if name in {"physical", "build", "variant_build"}
                else None,
            )
        )
    return tuple(result)


def specialist_budgets(
    deployment: Deployment, request: SpecialistRequest
) -> tuple[TaskBudget, ...]:
    binding = deployment.value["professional"][request.capability]
    if request.capability == "flow":
        settings = binding.get("execution", {})
        defaults = preset("flow-stage")
        profile = {
            "threads": settings.get("threads", defaults["cpu_cores"]),
            "resources": {
                "memory_bytes": settings.get("memory_gib", defaults["memory_gib"])
                << 30,
                "processes": defaults["processes"],
            },
            "stage_timeout_seconds": settings.get(
                "stage_timeout_seconds", defaults["seconds"]
            ),
            "stage_resources": {
                name: {"memory_bytes": memory << 30}
                for name, memory in settings.get("stage_memory_gib", {}).items()
            },
        }
    elif request.capability == "eco":
        profile = {
            "cpu_cores": deployment.design(request.design)
            .get("orfs_execution", {})
            .get("cpu_cores", preset("orfs")["cpu_cores"]),
            "memory_gib": binding.get(
                "session_memory_gib", preset("eco-session")["memory_gib"]
            ),
            "timeout_seconds": request.seconds,
        }
    else:
        profile = json.loads(Path(binding["profile_template"]).read_text())
        profile["resources"]["physical"] = {
            "cpu_cores": profile["resources"]
            .get("physical", profile["resources"].get("build", {}))
            .get("cpu_cores", preset("code-physical")["cpu_cores"]),
            "memory_bytes": binding.get(
                "physical_memory_gib", preset("code-physical")["memory_gib"]
            )
            << 30,
            "processes": preset("code-physical")["processes"],
        }
    budgets = native_budgets(
        request.capability,
        profile,
        request.seconds,
        operation=request.operation,
        code_source=request.code_source is not None,
    )
    design = deployment.design(request.design)
    facts = design.get("fact_execution", {})
    common = (
        resolve_budget("specialist-input"),
        resolve_budget(
            "design-export",
            memory_gib=facts.get("memory_gib", preset("design-export")["memory_gib"]),
            seconds=facts.get("timeout_seconds", preset("design-export")["seconds"]),
        ),
    )
    if request.capability == "flow":
        # The existing deterministic Flow replay recipe explicitly runs eight threads.
        # Admit that real downstream requirement before starting native/model search.
        common += (
            resolve_budget(
                "flow-replay",
                memory_gib=design.get("orfs_execution", {}).get(
                    "memory_gib", preset("flow-replay")["memory_gib"]
                ),
                seconds=request.seconds,
            ),
        )
    return budgets + common


def ensure_specialist_plan(
    deployment: Deployment, request: SpecialistRequest, experiment: Path
) -> None:
    plan = plan_execution(
        deployment, request.design, specialist_budgets(deployment, request)
    )
    path = experiment / "execution-plan.json"
    if path.exists():
        # New facts may make public_resources available after an owned-startup preflight.
        # The original immutable plan stays intact; current capacity is checked above.
        saved = profile_document(path)
        expected_budgets = [
            {
                "kind": budget.kind,
                "limits": budget.limits.to_dict(),
                "timeout_seconds": budget.timeout_seconds,
                "native_threads": budget.native_threads,
            }
            for budget in plan.budgets
        ]
        if (
            saved.get("profile") != ref_payload(plan.profile_ref)
            or saved.get("policy") != ref_payload(plan.policy_ref)
            or saved.get("budgets") != expected_budgets
        ):
            raise BusinessInputError(
                "execution_plan_changed", str(path), "profile or policy differs"
            )
        return
    bind_execution_plan(plan, experiment)


def admit_native_profile(
    deployment: Deployment,
    request: SpecialistRequest,
    profile: dict[str, Any],
    *,
    threads: int | Mapping[str, int] | None = None,
) -> None:
    budgets = native_budgets(
        request.capability,
        profile,
        request.seconds,
        operation=request.operation,
        code_source=request.code_source is not None,
        threads=threads,
    )
    plan_execution(deployment, request.design, budgets)

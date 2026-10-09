"""Investigation CLI and host actions use the same persisted application."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient
from eda_toolkits.inputs import SnapshotExecutionClient
from openroad_platform_client import KernelClient
from pydantic import TypeAdapter

from query_agent.adapters.investigation.analysis import ToolkitAnalysis
from query_agent.adapters.investigation.data import ScopedDataReads
from query_agent.adapters.investigation.scope import resolve_requests
from query_agent.adapters.investigation.skills import InstalledInvestigationSkills
from query_agent.adapters.investigation.store import JsonInvestigationStore
from query_agent.adapters.judgment.investigation import JevInvestigationJudgment
from query_agent.adapters.llm.budget import CostLedger
from query_agent.adapters.llm.codex import CodexModel
from query_agent.adapters.llm.codex_host import CodexInvestigationHost
from query_agent.adapters.llm.flash import DeepSeekFlashModel
from query_agent.application.investigation import (
    InvestigationBudgetExceeded,
    InvestigationService,
)
from query_agent.domain.handoff import BufferPermission, HandoffPackage
from query_agent.domain.investigation import (
    InvestigationBudget,
    InvestigationDecision,
    InvestigationState,
)
from query_agent.ports.investigation import InvestigationModel


def service(args: argparse.Namespace) -> InvestigationService:
    root = args.state_root.resolve()
    client = EdaAiClient(args.data_url, kernel_url=args.kernel_url, timeout=30)
    reader = ScopedDataReads(
        client, root / "evidence", KernelClient(args.kernel_url, timeout=30)
    )
    execution = SnapshotExecutionClient(
        args.kernel_url,
        source_client=KernelClient(args.archive_kernel_url)
        if args.archive_kernel_url
        else None,
    )
    model: InvestigationModel | None = None
    judgment = None
    if args.jev:
        if not args.jev_launcher or not args.jev_pricing or not args.cost_ledger:
            raise ValueError("JEV needs launcher, pricing and the shared cost ledger")
        judgment = JevInvestigationJudgment(
            launcher=args.jev_launcher,
            pricing=args.jev_pricing,
            ledger=CostLedger(args.cost_ledger),
            trace_root=root / "judgment-traces",
        )
    if args.model == "codex" and args.codex_mode == "turns":
        model = CodexModel(trace_root=root / "model-traces")
    elif args.model == "flash":
        if args.flash_config is None:
            raise ValueError(
                "Flash needs an explicit config referencing a user-only credential file"
            )
        if args.cost_ledger is None or not args.cost_ledger.is_file():
            raise ValueError("Flash requires an existing shared --cost-ledger")
        model = DeepSeekFlashModel(
            config=args.flash_config,
            max_output_tokens=8192,
            trace_root=root / "model-traces",
            ledger=CostLedger(args.cost_ledger),
        )
    return InvestigationService(
        data=reader,
        analysis=ToolkitAnalysis(client, execution, reader),
        store=JsonInvestigationStore(root / "investigations"),
        skills=InstalledInvestigationSkills(),
        model=model,
        judgment=judgment,
        handoff_permissions=TypeAdapter(
            dict[str, list[BufferPermission]]
        ).validate_json(args.handoff_permissions.read_text())
        if args.handoff_permissions
        else None,
    )


def add_commands(commands: Any) -> None:
    for name in (
        "investigate",
        "resume",
        "context",
        "act",
        "poll",
        "state",
        "evidence",
        "export-handoff",
        "receive-handoff",
    ):
        parser = commands.add_parser(name)
        parser.add_argument("--data-url", default="http://127.0.0.1:18924")
        parser.add_argument("--kernel-url", default="http://127.0.0.1:18700")
        parser.add_argument("--archive-kernel-url")
        parser.add_argument(
            "--state-root", type=Path, required=name != "receive-handoff"
        )
        parser.add_argument(
            "--model", choices=("codex", "flash", "host"), default="host"
        )
        parser.add_argument("--flash-config", type=Path)
        parser.add_argument("--cost-ledger", type=Path)
        parser.add_argument("--jev", action="store_true")
        parser.add_argument("--jev-launcher", type=Path)
        parser.add_argument("--jev-pricing", type=Path)
        parser.add_argument("--handoff-permissions", type=Path)
        parser.add_argument("--steps", type=int)
        parser.add_argument(
            "--codex-mode", choices=("hosted", "turns"), default="turns"
        )
        parser.add_argument(
            "--output", choices=("state", "context", "observation"), default="state"
        )
        if name == "investigate":
            parser.add_argument("question")
            scopes = parser.add_mutually_exclusive_group(required=True)
            scopes.add_argument("--snapshot", action="append")
            scopes.add_argument("--scope-request", type=Path)
            parser.add_argument("--max-seconds", type=float, default=180)
            parser.add_argument("--max-analyses", type=int, default=2)
            parser.add_argument("--no-skills", action="store_true")
        elif name != "receive-handoff":
            parser.add_argument("investigation_id")
        if name == "act":
            parser.add_argument("--decision", type=Path, required=True)
        if name == "evidence":
            parser.add_argument("--evidence-id", required=True)
            parser.add_argument("--offset", type=int, default=0)
            parser.add_argument("--max-characters", type=int, default=6000)
        if name == "export-handoff":
            parser.add_argument("--snapshot", required=True)
            parser.add_argument(
                "--role", choices=("eco", "flow", "code"), required=True
            )
            parser.add_argument("--objective", required=True)
            parser.add_argument("--buffer-permissions", type=Path)
            parser.add_argument("--package-output", type=Path, required=True)
        if name == "receive-handoff":
            parser.add_argument("--package", type=Path, required=True)
            parser.add_argument("--package-sha256", required=True)
            parser.add_argument("--proposal", type=Path, required=True)
            parser.add_argument("--receiver-output", type=Path, required=True)


def run_command(args: argparse.Namespace) -> int:
    if args.command == "receive-handoff":
        from query_agent.adapters.handoff.eco import EcoReceiver

        payload = args.package.read_bytes()
        if hashlib.sha256(payload).hexdigest() != args.package_sha256:
            raise ValueError("handoff package bytes changed after dispatch")
        receiver = EcoReceiver(
            EdaAiClient(args.data_url),
            SnapshotExecutionClient(args.kernel_url),
            args.receiver_output,
        )
        result = receiver.run(
            HandoffPackage.model_validate_json(payload),
            json.loads(args.proposal.read_text()),
        )
        print(json.dumps(result, indent=2))
        return 0
    application = service(args)
    state: InvestigationState
    before_evidence = before_operation = 0
    if args.command == "investigate":
        snapshot_ids = args.snapshot
        if args.scope_request is not None:
            resolution = resolve_requests(
                EdaAiClient(args.data_url, timeout=30),
                json.loads(args.scope_request.read_text()),
                question=args.question,
                output=args.state_root / "scope-requests",
            )
            if resolution["status"] != "resolved":
                print(json.dumps(resolution, indent=2))
                return 2
            snapshot_ids = resolution["snapshot_ids"]
        state = application.create(
            args.question,
            snapshot_ids,
            budget=InvestigationBudget(
                max_seconds=args.max_seconds, max_analyses=args.max_analyses
            ),
            use_skills=not args.no_skills,
        )
        if args.model != "host":
            state = run_model(args, application, state)
    else:
        state = application.store.load(args.investigation_id)
        before_evidence, before_operation = len(state.evidence), len(state.operations)
        if args.command == "resume":
            state = run_model(args, application, state)
        elif args.command == "act":
            try:
                state = application.apply(
                    state,
                    InvestigationDecision.model_validate_json(
                        args.decision.read_text()
                    ),
                )
            except InvestigationBudgetExceeded as exc:
                state = application.stop_for_budget(state, exc)
        elif args.command == "poll":
            state = application.poll(state)
        elif args.command == "context":
            print(
                application.observation(state)
                if args.output == "observation"
                else application.context(state)
            )
            return 0
        elif args.command == "evidence":
            print(
                json.dumps(
                    application.retrieve_evidence(
                        state,
                        evidence_id=args.evidence_id,
                        offset=args.offset,
                        max_characters=args.max_characters,
                    ),
                    ensure_ascii=False,
                )
            )
            return 0
        elif args.command == "export-handoff":
            permissions = (
                [
                    BufferPermission.model_validate(item)
                    for item in json.loads(args.buffer_permissions.read_text())
                ]
                if args.buffer_permissions
                else []
            )
            package = application.export_handoff(
                state,
                snapshot_id=args.snapshot,
                role=args.role,
                objective=args.objective,
                permissions=permissions,
            )
            args.package_output.parent.mkdir(parents=True, exist_ok=True)
            args.package_output.write_text(package.model_dump_json(indent=2) + "\n")
            print(package.model_dump_json(indent=2))
            return 0
    if args.output == "observation":
        print(
            application.observation(
                state, after_evidence=before_evidence, after_operation=before_operation
            )
        )
        return 0 if state.status not in ("failed", "stopped") else 1
    print(
        application.context(state)
        if args.output == "context"
        else state.model_dump_json(indent=2)
    )
    return 0 if state.status not in ("failed", "stopped") else 1


def run_model(
    args: argparse.Namespace,
    application: InvestigationService,
    state: InvestigationState,
) -> InvestigationState:
    if args.model == "codex" and args.codex_mode == "hosted":
        options = [
            "--state-root",
            str(args.state_root.resolve()),
            "--data-url",
            args.data_url,
            "--kernel-url",
            args.kernel_url,
            "--model",
            "host",
        ]
        if args.archive_kernel_url:
            options.extend(["--archive-kernel-url", args.archive_kernel_url])
        if args.handoff_permissions:
            options.extend(
                ["--handoff-permissions", str(args.handoff_permissions.resolve())]
            )
        if args.jev:
            options.extend(
                [
                    "--jev",
                    "--jev-launcher",
                    str(args.jev_launcher.resolve()),
                    "--jev-pricing",
                    str(args.jev_pricing.resolve()),
                    "--cost-ledger",
                    str(args.cost_ledger.resolve()),
                ]
            )
        return CodexInvestigationHost(
            trace_root=args.state_root.resolve() / "host-traces",
            program=[sys.executable, "-m", "query_agent"],
            action_options=options,
            state_root=args.state_root,
        ).run(application, state)
    return application.run(state.investigation_id, max_iterations=args.steps)

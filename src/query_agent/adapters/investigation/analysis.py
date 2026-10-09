"""Toolkit submission and explicit DF import over installed public boundaries."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any, cast

from eda_ai_client import EdaAiClient
from eda_toolkits.inputs import SnapshotExecutionClient
from eda_toolkits.jobs import timing_task

from query_agent.domain.evidence import (
    Evidence,
    EvidenceLevel,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    JsonValue,
)
from query_agent.domain.investigation import AnalysisRequest, AnalysisTicket, FixedScope

from .data import ScopedDataReads


class ToolkitAnalysis:
    def __init__(
        self,
        data: EdaAiClient,
        execution: SnapshotExecutionClient,
        scope_reader: ScopedDataReads,
    ) -> None:
        self.data, self.execution, self.scope_reader = data, execution, scope_reader
        self._deadline: float | None = None

    def set_timeout(self, seconds: float) -> None:
        self._deadline = time.monotonic() + seconds
        self.execution.set_timeout(seconds)

    def _remaining(self) -> float:
        remaining = 30 if self._deadline is None else self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("analysis operation exceeded its time budget")
        self.data.timeout = min(30, remaining)
        return min(30, remaining)

    def submit(
        self, request: AnalysisRequest, scopes: list[FixedScope]
    ) -> AnalysisTicket:
        if request.snapshot_id not in {scope.snapshot_id for scope in scopes}:
            raise ValueError("analysis must use a fixed investigation scope")
        if request.request_id is None or request.created_at is None:
            raise ValueError(
                "analysis needs a persisted request identity before submission"
            )
        self._remaining()
        response = self.data.read_query(
            "/snapshots/" + request.snapshot_id + "/summary",
            parameters={"detail": "full"},
        )
        snapshot = response["data"]["snapshot"]
        options: dict[str, Any] = {
            "path_count": request.path_count,
            "endpoint_path_count": request.endpoint_path_count,
        }
        for field in ("from_pin", "to_pin", "path_group"):
            value = getattr(request, field)
            if value is not None:
                options[field] = value
        task = timing_task(
            snapshot,
            options,
            analysis_id=request.request_id,
            created_at=request.created_at.isoformat(),
        )
        task["timeout_seconds"] = request.timeout_seconds
        result = self.execution.submit(task, idempotency_key=request.request_id)["run"]
        return AnalysisTicket(
            run_id=result["run_id"],
            snapshot_id=task["inputs"]["snapshot_id"],
            parent_snapshot_id=request.snapshot_id,
            request=request,
            status=result["status"],
        )

    def poll(self, ticket: AnalysisTicket) -> tuple[AnalysisTicket, FixedScope | None]:
        run = self.execution.run(ticket.run_id)
        updated = ticket.model_copy(update={"status": run["status"]})
        if run["status"] in ("failed", "timed_out", "cancelled", "lost"):
            logs = self.execution.logs(ticket.run_id, max_bytes=32768)
            content = cast(dict[str, JsonValue], {"run": run, "logs": logs})
            payload = json.dumps(content, ensure_ascii=False, indent=2).encode()
            digest = hashlib.sha256(payload).hexdigest()
            evidence_id = "ev-execution-" + digest[:24]
            (self.scope_reader.evidence_root / (evidence_id + ".json")).write_bytes(
                payload
            )
            evidence = Evidence(
                evidence_id=evidence_id,
                source_kind=EvidenceSourceKind.EXECUTION_RUN,
                level=EvidenceLevel.RUN_RECORD,
                content=content,
                scope=EvidenceScope(
                    snapshot_id=ticket.snapshot_id, run_id=ticket.run_id
                ),
                locator=EvidenceLocator(
                    uri=self.execution.base_url + "/kernel/runs/" + ticket.run_id
                ),
                provenance=EvidenceProvenance(
                    provider="execution-foundation",
                    source_hash=digest,
                    retrieved_at=datetime.now(UTC),
                ),
            )
            return updated.model_copy(update={"failure_evidence": evidence}), None
        if run["status"] != "succeeded":
            return updated, None
        self._import(ticket.run_id)
        self._remaining()
        response = self.data.read_query(
            "/snapshots/" + ticket.snapshot_id + "/summary",
            parameters={"detail": "full"},
        )
        context = response["data"]["run_summary"].get("timing_context", {})
        if context.get("parent_snapshot_id") != ticket.parent_snapshot_id:
            raise ValueError("analysis result belongs to a different fixed parent")
        self._remaining()
        scope = self.scope_reader.resolve_scope(
            ticket.snapshot_id, "supplement"
        ).model_copy(update={"parent_snapshot_id": ticket.parent_snapshot_id})
        return updated, scope

    def cancel(self, ticket: AnalysisTicket) -> AnalysisTicket:
        run = self.execution.cancel(ticket.run_id)["run"]
        return ticket.model_copy(update={"status": run["status"]})

    def _import(self, run_id: str) -> None:
        # DI remains a query SDK. Result import is an explicitly named DF write.
        request = urllib.request.Request(
            self.data.data_url + "/timing-queries/" + run_id + "/import",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=self._remaining()) as response:
            result = cast(dict[str, Any], json.load(response))
        if result.get("data", result).get("status") != "succeeded":
            raise ValueError("DF did not confirm successful analysis import")

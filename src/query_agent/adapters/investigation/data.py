"""Scoped DI reads return typed evidence and retain the complete wire response."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from eda_ai_client import EdaAiClient
from openroad_platform_client import KernelClient

from query_agent.domain.evidence import (
    Evidence,
    EvidenceLevel,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
    JsonValue,
)
from query_agent.domain.investigation import FixedScope, ReadOperation


class ScopedDataReads:
    def set_timeout(self, seconds: float) -> None:
        self.client.timeout = min(30, max(0.01, seconds))
        if self.execution is not None:
            self.execution.timeout = self.client.timeout

    def __init__(
        self,
        client: EdaAiClient,
        evidence_root: Path,
        execution: KernelClient | None = None,
    ) -> None:
        self.client, self.evidence_root = client, evidence_root.resolve()
        self.execution = execution
        self.evidence_root.mkdir(parents=True, exist_ok=True)

    def resolve_scope(self, snapshot_id: str, role: str) -> FixedScope:
        if role not in ("baseline", "candidate", "supplement", "subject"):
            raise ValueError("unknown investigation scope role")
        response = self.client.resolve_scope(snapshot_id=snapshot_id, origin="all")
        scope = response["data"]["snapshot"]
        return FixedScope(
            **scope,
            role=role,
        )

    def read(self, operation: ReadOperation, scopes: list[FixedScope]) -> Evidence:
        parsed = urlsplit(operation.path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(
                "read path must be a local contract path with separate arguments"
            )
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if parts and parts[0] == "executions":
            return self._execution_read(operation, parts, scopes)
        known = {scope.snapshot_id: scope for scope in scopes}
        if len(parts) < 3 or parts[0] != "snapshots" or parts[1] not in known:
            raise ValueError("read must belong to a fixed investigation snapshot")
        if (
            "analyses" in parts
            or "native-queries" in parts
            or "timing-queries" in parts
        ):
            raise ValueError(
                "reading cannot create analysis; use the explicit analysis action"
            )
        if "compare" in parts and (len(parts) < 4 or parts[3] not in known):
            raise ValueError("comparison target must be fixed in this investigation")
        if (
            len(parts) >= 4
            and parts[2] == "compare"
            and known[parts[1]].role == "candidate"
            and known[parts[3]].role == "baseline"
        ):
            raise ValueError(
                "investigation comparisons use baseline -> candidate so deltas "
                "are candidate minus baseline; reverse these snapshot IDs and "
                "select the corresponding source path from the baseline"
            )
        arguments = {arg.name: arg.value for arg in operation.arguments}
        if len(arguments) != len(operation.arguments):
            raise ValueError("read operation has duplicate argument names")
        response = self.client.read_query(operation.path, parameters=arguments)
        scope = known[parts[1]]
        for reported_scope in (
            response.get("scope", {}),
            response.get("data", {}).get("snapshot", {}),
        ):
            for name in ("snapshot_id", "design_id", "run_id", "revision_id", "stage"):
                if reported_scope.get(name) not in (None, getattr(scope, name)):
                    raise ValueError("provider response changed the fixed " + name)
        status = response.get("status", "unavailable")
        availability = {
            "available": EvidenceStatus.SUFFICIENT,
            "partial": EvidenceStatus.PARTIAL,
            # Pagination preserves observed rows, but not complete-domain coverage.
            "truncated": EvidenceStatus.PARTIAL,
            "unavailable": EvidenceStatus.INSUFFICIENT,
            "not_found": EvidenceStatus.INSUFFICIENT,
            "ambiguous": EvidenceStatus.CONFLICTING,
            "incomparable": EvidenceStatus.CONFLICTING,
        }
        evidence_id = "ev-" + uuid.uuid4().hex
        payload = json.dumps(response, ensure_ascii=False, indent=2).encode()
        source = self.evidence_root / (evidence_id + ".json")
        source.write_bytes(payload)
        return Evidence(
            evidence_id=evidence_id,
            source_kind=EvidenceSourceKind.DESIGN_DATA,
            level=EvidenceLevel.DIRECT_EXCERPT
            if "excerpt" in parts
            or (
                "fragments" in parts
                and response.get("data", {}).get("available", 0) > 0
            )
            else EvidenceLevel.PARSED_METRIC,
            content=cast(JsonValue, response),
            scope=EvidenceScope(
                **scope.model_dump(exclude={"role", "parent_snapshot_id"})
            ),
            locator=EvidenceLocator(
                uri=self.client.data_url + operation.path,
                section=json.dumps(arguments, sort_keys=True),
            ),
            provenance=EvidenceProvenance(
                provider="data-interface",
                source_hash=hashlib.sha256(payload).hexdigest(),
                retrieved_at=datetime.now(UTC),
            ),
            status=availability.get(status, EvidenceStatus.INSUFFICIENT),
            reason=None
            if status == "available"
            else str(response.get("missing", status)),
        )

    def _execution_read(
        self, operation: ReadOperation, parts: list[str], scopes: list[FixedScope]
    ) -> Evidence:
        if self.execution is None or len(parts) < 2:
            raise ValueError("execution evidence reader is not configured")
        run_id = parts[1]
        run = self.execution.run(run_id)
        labels = run.get("labels", {})
        parents = {
            labels.get(key)
            for key in ("parent_snapshot_id", "experiment_parent_snapshot_id")
            if labels.get(key) is not None
        }
        related = [
            scope
            for scope in scopes
            if scope.design_id == run.get("design_id")
            and (
                (parents and parents == {scope.snapshot_id})
                or scope.run_id == run_id
                or (not parents and scope.run_id == labels.get("analysis_of_run_id"))
            )
        ]
        if not related:
            raise ValueError("execution does not belong to a fixed investigation scope")
        args = {arg.name: arg.value for arg in operation.arguments}
        if len(args) != len(operation.arguments) or set(args) - {"offset", "max_bytes"}:
            raise ValueError("execution reads accept offset and max_bytes only")
        offset, limit = int(args.get("offset", "0")), int(args.get("max_bytes", "8192"))
        if offset < 0 or not 1 <= limit <= 65536:
            raise ValueError("invalid execution excerpt range")
        suffix = parts[2:]
        content: dict[str, Any]
        level = EvidenceLevel.RUN_RECORD
        if not suffix:
            content = {"run": run}
        elif suffix == ["logs"]:
            content = self.execution.logs(run_id, offset=offset, max_bytes=limit)
        elif suffix == ["resources"]:
            content = self.execution.resources(run_id)
        elif suffix == ["artifacts"]:
            content = {"artifacts": self.execution.artifacts(run_id)}
        elif len(suffix) == 3 and suffix[0] == "artifacts" and suffix[2] == "excerpt":
            refs = [
                ref
                for ref in self.execution.artifacts(run_id)
                if ref["artifact_id"] == suffix[1]
            ]
            if len(refs) != 1:
                raise ValueError("artifact is not attached to the scoped execution")
            excerpt = self.execution.artifact_excerpt(
                run_id, suffix[1], offset=offset, max_bytes=limit
            )
            if excerpt["sha256"] != refs[0]["sha256"]:
                raise ValueError("execution artifact changed after registration")
            content = {"source": refs[0], "excerpt": excerpt}
            level = EvidenceLevel.DIRECT_EXCERPT
        else:
            raise ValueError("unknown read-only execution evidence path")
        payload = json.dumps(content, ensure_ascii=False, indent=2).encode()
        evidence_id = "ev-" + uuid.uuid4().hex
        (self.evidence_root / (evidence_id + ".json")).write_bytes(payload)
        scope = related[0]
        return Evidence(
            evidence_id=evidence_id,
            source_kind=EvidenceSourceKind.EXECUTION_RUN,
            level=level,
            content=cast(JsonValue, content),
            scope=EvidenceScope(
                **scope.model_dump(exclude={"role", "parent_snapshot_id"})
            ),
            locator=EvidenceLocator(
                uri=self.execution.base_url + "/kernel/runs/" + run_id,
                section=operation.path,
            ),
            provenance=EvidenceProvenance(
                provider="execution-foundation",
                source_hash=hashlib.sha256(payload).hexdigest(),
                retrieved_at=datetime.now(UTC),
            ),
            status=EvidenceStatus.PARTIAL
            if content.get("truncated") or content.get("excerpt", {}).get("truncated")
            else EvidenceStatus.SUFFICIENT,
        )

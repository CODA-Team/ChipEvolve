"""HTTP translation layer for the kernel."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openroad_platform_contracts import ContractError, TaskSpec
from openroad_platform_provenance import EvidenceIndex
from openroad_platform_provenance.index import DEFAULT_RUN_LIMIT
from openroad_platform_registry import PluginRegistry, RegistryError
from openroad_platform_runtime import (
    ArtifactInventory,
    InputStagingError,
    LogQuery,
    ResourceLimitsUnsupported,
    ResourceQuery,
    RuntimeStore,
    RuntimeStoreError,
    WorkflowRuntime,
    queue_health,
    worker_health,
)
from openroad_platform_runtime.bundle import export_run_bundle

from .router import MAX_RESPONSE_BYTES, HttpError, Request, Response, Router

MAX_INPUT_UPLOAD_BYTES = 64 * 1024**3
INPUT_UPLOAD_TTL_SECONDS = 24 * 60 * 60


@dataclass
class KernelApi:
    """The kernel objects, exposed over HTTP."""

    store: RuntimeStore
    runtime: WorkflowRuntime
    registry: PluginRegistry
    index: EvidenceIndex
    evaluator_error: str | None = None
    #: The directory every artifact path must resolve inside.  A locator that
    #: cannot prove containment refuses instead of answering.
    state_root: Path | None = None

    # -- registration -----------------------------------------------------

    def register(self, router: Router) -> None:
        router.get("/kernel/health", self.health)

        router.get("/kernel/plugins", self.plugins)

        router.post("/kernel/inputs", self.ingest_input)
        router.post("/kernel/inputs/chunk", self.ingest_input_chunk)
        router.post("/kernel/runs", self.submit_run)
        router.get("/kernel/runs", self.list_runs)
        router.get("/kernel/runs/{run_id}", self._run_handler(self.get_run))
        router.get("/kernel/designs/{design_id}/tree", self.design_tree)
        router.post("/kernel/runs/{run_id}/cancel", self._run_handler(self.cancel_run))
        router.post("/kernel/runs/{run_id}/retry", self._run_handler(self.retry_run))
        router.post("/kernel/runs/{run_id}/bundle", self._run_handler(self.bundle))
        router.get("/kernel/runs/{run_id}/metrics", self._run_handler(self.metrics))
        router.get("/kernel/runs/{run_id}/artifacts", self._run_handler(self.artifacts))
        router.get("/kernel/runs/{run_id}/timeline", self._run_handler(self.timeline))
        router.get("/kernel/runs/{run_id}/resources", self._run_handler(self.resources))
        router.get("/kernel/runs/{run_id}/logs", self._run_handler(self.logs))
        router.get(
            "/kernel/runs/{run_id}/artifacts/{artifact_id}/excerpt",
            self._run_handler(self.artifact_excerpt),
        )
        router.get(
            "/kernel/runs/{run_id}/artifacts/{artifact_id}/download",
            self._run_handler(self.artifact_download),
        )
        router.get(
            "/kernel/runs/{run_id}/artifacts/{artifact_id}/chunk",
            self._run_handler(self.artifact_chunk),
        )
        router.get(
            "/kernel/runs/{run_id}/artifacts/{artifact_id}/locator",
            self._run_handler(self.artifact_locator),
        )
        router.get("/kernel/graph", self.graph)

    def _require_run(self, run_id: str) -> None:
        try:
            self.store.get_run(run_id)
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc

    def _run_handler(
        self, handler: Callable[[Request], Response]
    ) -> Callable[[Request], Response]:
        def checked(request: Request) -> Response:
            self._require_run(request.params["run_id"])
            return handler(request)

        return checked

    # -- health and catalogue ---------------------------------------------

    def health(self, request: Request) -> Response:
        return Response.json(
            {
                "service": "kernel",
                "status": "ok",
                "plugins": len(self.registry.list()),
                "admitted": sum(1 for p in self.registry.list() if p.executable),
                "evaluator": {
                    "status": (
                        "ready" if self.evaluator_error is None else "unavailable"
                    ),
                    **({"error": self.evaluator_error} if self.evaluator_error else {}),
                },
                "workers": worker_health(self.store),
                "queue": queue_health(self.store),
            }
        )

    def plugins(self, request: Request) -> Response:
        return Response.json({"plugins": self.registry.catalogue()})

    def ingest_input(self, request: Request) -> Response:
        if not isinstance(request.body, bytes):
            raise HttpError(400, "input upload requires application/octet-stream")
        uploaded = self.store.ingest_input(request.body)
        return Response.json({"input": uploaded.to_dict()}, status=201)

    def ingest_input_chunk(self, request: Request) -> Response:
        if not isinstance(request.body, bytes):
            raise HttpError(400, "input upload requires application/octet-stream")
        upload_id = request.q("upload_id") or ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", upload_id):
            raise HttpError(400, "upload_id must be a random opaque token")
        offset = request.q_int("offset", 0) or 0
        if offset < 0:
            raise HttpError(400, "offset must not be negative")
        directory = self.store.objects_root / "uploads"
        path = directory / upload_id
        directory.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - INPUT_UPLOAD_TTL_SECONDS
        for stale in directory.iterdir():
            if stale.is_file() and stale.stat().st_mtime < cutoff:
                stale.unlink(missing_ok=True)
        current = path.stat().st_size if path.is_file() else 0
        if current != offset:
            raise HttpError(409, f"upload offset is {current}, not {offset}")
        if current + len(request.body) > MAX_INPUT_UPLOAD_BYTES:
            raise HttpError(413, "input upload exceeds the 64 GiB limit")
        with path.open("ab") as output:
            output.write(request.body)
        if not request.q_bool("final"):
            return Response.json(
                {"upload_id": upload_id, "offset": current + len(request.body)}
            )
        try:
            uploaded = self.store.ingest_input_file(path)
        finally:
            path.unlink(missing_ok=True)
        return Response.json({"input": uploaded.to_dict()}, status=201)

    # -- runs -------------------------------------------------------------

    def submit_run(self, request: Request) -> Response:
        body = _object(request)
        task_payload = body.get("task")
        if not isinstance(task_payload, dict):
            raise HttpError(400, "body must contain a task object")
        try:
            task = TaskSpec.from_dict(task_payload)
        except ContractError as exc:
            raise HttpError(400, str(exc)) from exc

        try:
            idempotency_key = request.q("idempotency_key")
            run = (
                self.runtime.submit_idempotent(task, idempotency_key=idempotency_key)
                if request.q("idempotent") or idempotency_key
                else self.runtime.submit(task)
            )
        except (
            RegistryError,
            InputStagingError,
            ResourceLimitsUnsupported,
            ValueError,
        ) as exc:
            # A task naming a capability that is not available, or inputs that
            # are not where it said, is the caller's mistake, not the server's.
            # Unhandled, this reached the client as a 500, which sends an
            # operator to investigate the platform for a problem that is in
            # their own request.
            raise HttpError(400, str(exc)) from exc
        except RuntimeStoreError as exc:
            raise HttpError(409 if idempotency_key else 500, str(exc)) from exc
        return Response.json({"run": self._run_detail(run.run_id)}, status=201)

    def list_runs(self, request: Request) -> Response:
        limit = request.q_int("limit")
        offset = request.q_int("offset", 0) or 0
        try:
            summaries = self.index.runs(
                project_id=request.q("project_id"),
                design_id=request.q("design_id"),
                plugin_id=request.q("plugin_id"),
                status=request.q("status"),
                run_type=request.q("run_type"),
                analysis_of_run_id=request.q("analysis_of_run_id"),
                offset=offset,
                limit=limit if limit is not None else DEFAULT_RUN_LIMIT,
            )
        except ValueError as exc:
            raise HttpError(400, str(exc)) from exc

        return Response.json({"runs": [s.to_dict() for s in summaries]})

    def get_run(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        try:
            return Response.json({"run": self._run_detail(run_id)})
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc

    def design_tree(self, request: Request) -> Response:
        design_id = request.params["design_id"]
        offset = request.q_int("offset", 0) or 0
        limit = request.q_int("limit", 500) or 500
        if not 1 <= limit <= 500:
            raise HttpError(400, "limit must be between 1 and 500")
        summaries = self.index.runs(
            design_id=design_id,
            offset=offset,
            limit=min(limit + 1, 500),
        )
        has_more = len(summaries) > limit or (limit == 500 and len(summaries) == 500)
        summaries = summaries[:limit]
        total = self.index.count_runs(design_id=design_id)
        revisions: dict[str, dict[str, Any]] = {}
        for summary in summaries:
            revision = summary.design_revision_id or "unversioned"
            node = self._run_detail(summary.run_id)
            revisions.setdefault(
                revision,
                {
                    "design_revision_id": summary.design_revision_id,
                    "runs": [],
                },
            )["runs"].append(node)
        return Response.json(
            {
                "design_id": design_id,
                "revisions": list(revisions.values()),
                "run_count": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "next_offset": offset + limit if has_more else None,
            }
        )

    def _run_detail(self, run_id: str) -> dict[str, Any]:
        """The run, plus the one thing a queued run cannot currently say.

        ``queued`` looks the same whether the machine is full, whether no worker
        is running, or whether something is stuck -- and those need three
        different responses from whoever is looking.  The platform knows which,
        so it says, rather than making an operator open the database to find out.
        """
        detail = self.index.run_detail(run_id)
        detail["waiting_for"] = ResourceQuery(
            self.store, self.runtime.config
        ).waiting_for(run_id)
        return detail

    def cancel_run(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        try:
            self.store.request_cancel(run_id)
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc
        return Response.json({"run": self._run_detail(run_id)})

    def retry_run(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        body = _object(request)
        reason = str(body.get("reason") or "")
        try:
            detail = self.store.request_retry(run_id, requester="local", reason=reason)
        except (RuntimeStoreError, ValueError) as exc:
            raise HttpError(400, str(exc)) from exc
        return Response.json({"run": detail}, status=202)

    def bundle(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        try:
            return Response.json(
                {"bundle": export_run_bundle(self.store, run_id)}, status=201
            )
        except RuntimeStoreError as exc:
            raise HttpError(409, str(exc)) from exc

    def metrics(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        entries = self.index.metrics(
            run_id, complete_only=request.q_bool("complete_only")
        )
        return Response.json({"metrics": [m.to_dict() for m in entries]})

    def artifacts(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        return Response.json(
            {
                "artifacts": ArtifactInventory(self.store).for_run(
                    run_id,
                    category=request.q("category"),
                    format=request.q("format"),
                    stage=request.q("stage"),
                    kind=request.q("kind"),
                )
            }
        )

    def timeline(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        return Response.json({"timeline": self.index.timeline(run_id)})

    def resources(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        try:
            return Response.json(
                {
                    "resources": ResourceQuery(self.store, self.runtime.config).run(
                        run_id
                    )
                }
            )
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc

    def logs(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        try:
            view = LogQuery(self.store).run(
                run_id,
                offset=request.q_int("offset", 0) or 0,
                max_bytes=request.q_int("max_bytes"),
            )
        except (RuntimeStoreError, ValueError) as exc:
            raise HttpError(
                404 if isinstance(exc, RuntimeStoreError) else 400, str(exc)
            ) from exc
        return Response.json({"logs": view})

    def artifact_excerpt(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        offset = request.q_int("offset", 0) or 0
        max_bytes = request.q_int("max_bytes", 8192) or 8192
        try:
            excerpt = self.runtime.read_artifact_excerpt(
                run_id,
                request.params["artifact_id"],
                offset=offset,
                max_bytes=max_bytes,
            )
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc
        except ValueError as exc:
            raise HttpError(400, str(exc)) from exc
        return Response.json(excerpt)

    def artifact_download(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        artifact_id = request.params["artifact_id"]
        detail = self.index.run_detail(run_id)
        artifacts = [
            artifact
            for stage in detail.get("stages", ())
            for attempt in stage.get("attempts", ())
            for artifact in attempt.get("artifacts", ())
            if artifact.get("artifact_id") == artifact_id
        ]
        if len(artifacts) != 1:
            raise HttpError(404, "artifact not found")
        artifact = artifacts[0]
        if artifact["size_bytes"] > MAX_RESPONSE_BYTES:
            raise HttpError(413, "artifact exceeds the download response limit")
        try:
            path = self.store.artifact_path(artifact_id)
            content = path.read_bytes()
        except (OSError, RuntimeStoreError) as exc:
            raise HttpError(404, str(exc)) from exc
        from openroad_platform_runtime import sha256

        if (
            len(content) != artifact["size_bytes"]
            or sha256(content) != artifact["sha256"]
        ):
            raise HttpError(409, "artifact bytes no longer match the registered hash")
        return Response(
            body=content,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Artifact-SHA256": artifact["sha256"],
            },
        )

    def artifact_chunk(self, request: Request) -> Response:
        run_id = request.params["run_id"]
        offset = request.q_int("offset", 0) or 0
        size = request.q_int("max_bytes", 64 * 1024) or 64 * 1024
        try:
            return Response.json(
                self.runtime.read_artifact_excerpt(
                    run_id,
                    request.params["artifact_id"],
                    offset=offset,
                    max_bytes=size,
                    verify_hash=False,
                )
            )
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc
        except ValueError as exc:
            raise HttpError(400, str(exc)) from exc

    def artifact_locator(self, request: Request) -> Response:
        """Where an artifact's bytes already are on this host, without moving them.

        Reading a multi-hundred-megabyte stage through 64 KiB base64 chunks is
        thousands of round trips to fetch a file that is on the same disk.  This
        answers with the custody path instead of the bytes, so a same-host
        importer can open the file directly.

        The path is the store's own answer, never a caller's, and it must
        resolve inside the kernel state root: a locator that cannot prove
        containment refuses rather than answers.  The ``sha256`` is the
        registered hash and the size is re-checked on every call; the content is
        not re-read (``content_verified`` says so), so a reader that needs the
        hash proven hashes what it reads.
        """
        run_id = request.params["run_id"]
        artifact_id = request.params["artifact_id"]
        _require_path_segment(run_id, artifact_id)
        if self.state_root is None:
            raise HttpError(
                500, "kernel has no state root configured: refusing to locate artifacts"
            )
        try:
            view = self.runtime.describe(run_id)
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc
        matches = [
            (stage, attempt, artifact)
            for stage in view.get("stages", ())
            for attempt in stage.get("attempts", ())
            for artifact in attempt.get("artifacts", ())
            if artifact.get("artifact_id") == artifact_id
        ]
        if len(matches) != 1:
            # Membership, not mere existence: another run's artifact is not this
            # run's to hand out, and saying which is itself a disclosure.
            raise HttpError(
                404, f"artifact {artifact_id!r} is not registered in run {run_id!r}"
            )
        stage, attempt, artifact = matches[0]
        try:
            path = self.store.artifact_path(artifact_id)
        except RuntimeStoreError as exc:
            raise HttpError(404, str(exc)) from exc
        root = self.state_root.resolve()
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise HttpError(
                409, "artifact path resolves outside the kernel state root"
            ) from exc
        if not resolved.is_file():
            raise HttpError(404, "artifact bytes are missing from the store")
        size_bytes = resolved.stat().st_size
        if size_bytes != artifact["size_bytes"]:
            raise HttpError(409, "artifact bytes no longer match the registered size")
        return Response.json(
            {
                "locator": {
                    "run_id": run_id,
                    "artifact_id": artifact_id,
                    "stage_key": stage["stage_key"],
                    "attempt_id": attempt["attempt_id"],
                    "attempt_number": attempt["attempt_number"],
                    "kind": artifact["kind"],
                    "logical_path": artifact["store_key"],
                    "storage": artifact["storage"],
                    "path": str(resolved),
                    "state_root": str(root),
                    "size_bytes": size_bytes,
                    "sha256": artifact["sha256"],
                    "content_verified": False,
                }
            }
        )

    def graph(self, request: Request) -> Response:
        run_ids = request.q_all("run_id")
        if not run_ids:
            raise HttpError(400, "at least one run_id is required")
        for run_id in run_ids:
            self._require_run(run_id)
        return Response.json({"graph": self.index.artifact_graph(run_ids).to_dict()})


def _object(request: Request) -> dict[str, Any]:
    if not isinstance(request.body, dict):
        raise HttpError(400, "request body must be a JSON object")
    return request.body


def _require_path_segment(*values: str) -> None:
    """Refuse an identifier that is not a single path segment.

    A route template cannot match a value containing ``/``, but a
    percent-encoded one is decoded *after* matching, so ``%2e%2e%2f`` arrives
    here as ``../``.  Identifiers are database keys and the traversal could not
    reach a path join anyway; this makes the refusal explicit instead of
    incidental to a lookup miss.
    """
    for value in values:
        if not value or value in {".", ".."} or set(value) & {"/", "\\", "\x00"}:
            raise HttpError(400, "identifier must be a single path segment")

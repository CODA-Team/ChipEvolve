"""Read-only client for the EDA-AI Data Interface.

Standard library only.  It talks to the deployed Data Foundation over HTTP and
imports nothing from this repository's applications, so a partner can vendor or
install it without knowing how the service is built.

The tool surface follows CONTRACT.md v0.2.  Two rules from that document shape
every method here:

* a missing fact is never a silent empty value - the service reports a
  ``status`` and a ``missing`` list, and this client passes them through
  unchanged rather than flattening them into ``None``;
* evidence references are returned as-is, so a caller can follow them back to
  the raw artifact bytes through :meth:`EdaAiClient.artifact_bytes`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

__all__ = ["EdaAiClient", "EdaAiError", "DEFAULT_DATA_URL"]

DEFAULT_DATA_URL = "http://127.0.0.1:18924"


class EdaAiError(RuntimeError):
    """The service rejected a query, or answered with something unusable."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class EdaAiClient:
    """Deterministic EDA facts, through the public service boundary.

    ``data_url`` serves facts (CONTRACT tools 1-12).  ``kernel_url`` is the
    execution foundation, and is only needed for ``list_runs``,
    ``list_artifacts`` and ``artifact_bytes`` - a caller that only wants design
    facts can leave it unset.
    """

    data_url: str = DEFAULT_DATA_URL
    kernel_url: str | None = None
    timeout: float = 60.0

    def __post_init__(self) -> None:
        for name, value in (("data_url", self.data_url), ("kernel_url", self.kernel_url)):
            if value is not None and not str(value).startswith(("http://", "https://")):
                raise ValueError(f"{name} must be http(s)")
        self.data_url = self.data_url.rstrip("/")
        self.kernel_url = self.kernel_url.rstrip("/") if self.kernel_url else None

    # ------------------------------------------------------------------ health

    def health(self) -> dict[str, Any]:
        """Liveness of the data service."""
        return self._get(self.data_url, "/health")

    def read_query(self, path: str, *, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Read a documented service extension through the same wire contract.

        This escape hatch is transport only: DF validates query semantics,
        scope, units, paging and evidence. It never accepts an external URL.
        """
        parsed = urllib.parse.urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not path.startswith('/'):
            raise ValueError("read_query path must be an absolute local HTTP path without query or fragment")
        return self._get(self.data_url, path, parameters)

    def read_batch(self, requests: list[str], *, bindings: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ordered public read batch; no member can create an EDA analysis."""
        payload = {"requests": requests, "bindings": bindings or {}}
        return self._post("/query", payload)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        request = urllib.request.Request(self.data_url + path, data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        host = urllib.parse.urlsplit(self.data_url).hostname
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if host in {"localhost", "127.0.0.1", "::1"} else urllib.request.build_opener())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise EdaAiError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise EdaAiError(f"cannot reach data service: {exc.reason}") from exc
        except (ValueError, UnicodeError) as exc:
            raise EdaAiError("service returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise EdaAiError("service response must be a JSON object")
        return result

    # ------------------------------------------------------- tool 1: designs

    def list_designs(self) -> dict[str, Any]:
        """Authoritative design catalog; preserve the service envelope."""
        return self._get(self.data_url, "/designs")

    def resolve_scope(self, *, snapshot_id: str | None = None,
                      design_id: str | None = None, revision_id: str | None = None,
                      run_id: str | None = None, stage: str | None = None,
                      origin: str = "flow") -> dict[str, Any]:
        """Resolve exactly one immutable snapshot, or return candidates."""
        return self._get(self.data_url, "/scope", {
            "snapshot_id": snapshot_id, "design_id": design_id,
            "revision_id": revision_id, "run_id": run_id, "stage": stage,
            "origin": origin})

    def list_runs(self, *, design_id: str | None = None,
                  status: str | None = None, limit: int = 100,
                  offset: int = 0) -> list[dict[str, Any]]:
        """Execution catalog, filtered and paginated by its owning service.

        Stage snapshots are discovered through get_run_summary/resolve_scope.
        """
        self._require_kernel("list_runs")
        return self._get(self.kernel_url, "/kernel/runs", {
            "design_id": design_id, "status": status,
            "limit": limit, "offset": offset})["runs"]

    # ---------------------------------------------------- tool 3: run summary

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        """Every indexed stage snapshot of one run, with record counts."""
        return self._get(self.data_url, f"/runs/{_segment(run_id)}/summary")

    # -------------------------------------------------- tool 4: stage summary

    def get_stage_summary(self, snapshot_id: str) -> dict[str, Any]:
        """One immutable fact boundary: counts, coverage and source artifacts."""
        return self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/summary")

    # ----------------------------------------------------- tool 5: artifacts

    def list_artifacts(self, run_id: str, *, kind: str | None = None) -> list[dict[str, Any]]:
        """Registered raw artifacts of one run.  Needs ``kernel_url``."""
        self._require_kernel("list_artifacts")
        return self._get(self.kernel_url, f"/kernel/runs/{_segment(run_id)}/artifacts",
                         {"kind": kind})["artifacts"]

    # ------------------------------------------------------- tool 6: metrics

    def get_metrics(self, *, run_id: str | None = None, snapshot_id: str | None = None,
                    stage: str | None = None, name: str | None = None,
                    include_raw: bool = False, limit: int = 100,
                    offset: int = 0) -> dict[str, Any]:
        """Canonical metrics, with ownership/scoping enforced by the service."""
        if run_id is None and snapshot_id is None:
            raise ValueError("get_metrics needs run_id or snapshot_id")
        path = (f"/snapshots/{_segment(snapshot_id)}/metrics" if snapshot_id is not None
                else f"/runs/{_segment(run_id)}/metrics")
        return self._get(self.data_url, path, {
            "run_id": run_id if snapshot_id is not None else None,
            "stage": stage, "name": name, "limit": limit, "offset": offset,
            "include_raw": 1 if include_raw else None})

    # -------------------------------------------------- tool 7: timing paths

    def get_timing_paths(self, snapshot_id: str, *, check: str | None = None,
                         sort: str | None = None, order: str = "worst",
                         limit: int = 100, offset: int = 0,
                         detail: str = "summary") -> dict[str, Any]:
        """Timing path summaries; ``check`` filters setup/hold on the server.

        Filtering here instead used to break the pagination envelope: the count
        still described the unfiltered page, so ``check="hold"`` could report
        ``count=10, returned=0, truncated=true``.
        """
        params = {"limit": limit, "offset": offset, "check": check,
                  "sort": sort, "order": order, "detail": detail}
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/timing-paths",
                         {key: value for key, value in params.items()
                          if value is not None})

    # ------------------------------------------------ tool 8: one timing path

    def get_timing_path(self, snapshot_id: str, path_id: str,
                        *, include: str = "summary",
                        detail: str = "summary",
                        relation_limit: int = 200) -> dict[str, Any]:
        """One path.  ``include`` is ``summary``, ``points`` or ``context``.

        ``summary`` returns the path record; ``points`` returns the ordered
        points envelope for it; ``context`` returns the compiled path context
        with its objects, physical facts and evidence.
        """
        if include not in {"summary", "points", "context"}:
            raise ValueError("include must be summary, points or context")
        base = f"/snapshots/{_segment(snapshot_id)}/timing-paths/{_segment(path_id)}"
        if include == "summary":
            return self._get(self.data_url, base)
        if include == "points":
            return self._get(self.data_url, f"{base}/points")
        return self._get(self.data_url, f"{base}/context",
                         {"detail": detail, "relation_limit": relation_limit})

    # ----------------------------------------------------- tool 9: instances

    def get_timing_points(self, snapshot_id: str, *, path_id: str | None = None,
                          sort: str | None = None, order: str = "worst",
                          limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Timing points across the snapshot, rankable by slew or arrival.

        Points used to be reachable only through their path, so "the worst slew in
        the design" cost every point of every path.
        """
        params = {"limit": limit, "offset": offset, "order": order}
        if path_id:
            params["path_id"] = path_id
        if sort:
            params["sort"] = sort
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/timing-points", params)

    def get_object_context(self, snapshot_id: str, *, kind: str,
                           name: str | None = None, object_id: str | None = None,
                           detail: str = "summary", relation_limit: int = 200) -> dict[str, Any]:
        """Exact name or explicit ID; resolution and ambiguity belong to the service."""
        return self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/resolve-object",
                         {"kind": kind, "name": name, "object_id": object_id,
                          "detail": detail, "relation_limit": relation_limit})

    def get_instance(self, snapshot_id: str, name: str, *,
                     detail: str = "summary", relation_limit: int = 200) -> dict[str, Any]:
        """Instance context in the standard service envelope."""
        return self.get_object_context(snapshot_id, kind="instance", name=name,
                                       detail=detail, relation_limit=relation_limit)

    def get_net_context(self, snapshot_id: str, net: str, *, by: str = "name",
                        detail: str = "summary", relation_limit: int = 200) -> dict[str, Any]:
        """Net context; choose by=name or by=object_id explicitly."""
        if by not in {"name", "object_id"}:
            raise ValueError("by must be name or object_id")
        return self.get_object_context(snapshot_id, kind="net",
                                       **{by: net}, detail=detail,
                                       relation_limit=relation_limit)

    # --------------------------------------------- tool 11: physical context

    def get_physical_context(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        """Location, bbox, geometry and routing for one object."""
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/physical/{_segment(object_id)}")

    def query_objects(self, snapshot_id: str, **filters: str | int | float | bool) -> dict[str, Any]:
        """Public discovery filters; scope, complete counts and paging belong to DF."""
        return self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/objects", filters)

    def get_relationships(self, snapshot_id: str, object_id: str, *, kind: str,
                          limit: int = 200, offset: int = 0) -> dict[str, Any]:
        """Explicit relations and endpoint identities, with complete page counts."""
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/objects/{_segment(object_id)}/relationships",
                         {"kind": kind, "limit": limit, "offset": offset})

    def get_net_engineering(self, snapshot_id: str, net: str, *,
                            limit: int = 200, offset: int = 0) -> dict[str, Any]:
        """Native load/driver counts and explicit connectivity coverage."""
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/nets/{_segment(net)}/engineering",
                         {"limit": limit, "offset": offset})

    def get_path_engineering(self, snapshot_id: str, path_id: str,
                             **options: str | int) -> dict[str, Any]:
        """Path joins and increments are deterministic data-layer operations."""
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/timing-paths/{_segment(path_id)}/engineering",
                         options)

    # ---------------------------------------------------- tool 12: evidence

    def get_evidence(self, snapshot_id: str, *, record_type: str | None = None,
                     record_id: str | None = None, artifact_id: str | None = None,
                     limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Source locations behind the indexed facts.

        With ``record_type`` and ``record_id`` it returns that record's own
        evidence; otherwise it returns one page of the snapshot's evidence
        index, optionally filtered by ``artifact_id``.  The index is large, so
        the service streams it and reports ``count: None`` with
        ``count_status: "unavailable"`` when the total was not computed.
        """
        if record_type and record_id:
            return self._get(self.data_url,
                             f"/snapshots/{_segment(snapshot_id)}/records/"
                             f"{_segment(record_type)}/{_segment(record_id)}/evidence")
        # `record_type` used to be dropped here unless `record_id` came with it, so
        # a caller asking for one type silently got one page of the whole index.
        return self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/evidence",
                         {"artifact_id": artifact_id, "record_type": record_type,
                          "limit": limit, "offset": offset})

    def read_evidence(self, snapshot_id: str, record_type: str,
                      record_id: str) -> dict[str, Any]:
        """The raw fragment each evidence reference names, not the whole artifact.

        Whole-artifact download is capped at 4 MiB and a fact rarely needs a whole
        file, so this returns the slice - a timing check by path index, a timing
        point by index and ordinal, a mapping row by pin name - together with the
        artifact identity and hash it came from.  A source that cannot be sliced
        answers `unavailable` with the reason rather than something else.
        """
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/records/"
                         f"{_segment(record_type)}/{_segment(record_id)}/fragments")

    # ------------------------------------------------------------- raw bytes

    def artifact_bytes(self, run_id: str, artifact_id: str) -> bytes:
        """The original artifact bytes an evidence reference points at.

        Not part of the twelve tools: this reads the execution foundation, and
        the caller should verify the ``sha256`` from the evidence entry.
        """
        self._require_kernel("artifact_bytes")
        return self._get_bytes(self.kernel_url,
                               f"/kernel/runs/{_segment(run_id)}/artifacts/"
                               f"{_segment(artifact_id)}/download")

    # ------------------------------------------------------------------ plumbing

    def _require_kernel(self, tool: str) -> None:
        if not self.kernel_url:
            raise EdaAiError(
                f"{tool} reads the execution foundation; construct the client with "
                "kernel_url to use it")

    def _get(self, base: str, path: str,
             params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            result = json.loads(self._get_bytes(base, path, params))
        except (ValueError, UnicodeError) as exc:
            raise EdaAiError("service returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise EdaAiError("service response must be a JSON object")
        return result

    def _get_bytes(self, base: str, path: str,
                   params: dict[str, Any] | None = None) -> bytes:
        url = base + path
        if params:
            query = urllib.parse.urlencode({key: value for key, value in params.items()
                                            if value is not None})
            if query:
                url = f"{url}?{query}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            host = urllib.parse.urlsplit(url).hostname
            opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                      if host in {"localhost", "127.0.0.1", "::1"}
                      else urllib.request.build_opener())
            with opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise EdaAiError(f"HTTP {exc.code} from {url}: {detail}",
                             status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise EdaAiError(f"cannot reach {url}: {exc.reason}") from exc

    def close(self) -> None:  # pragma: no cover - symmetry for context managers
        """No persistent connection is held; provided for ``with`` symmetry."""

    def __enter__(self) -> "EdaAiClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _segment(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")

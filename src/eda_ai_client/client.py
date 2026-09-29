"""Read-only client for the EDA-AI Data Interface.

Standard library only.  It talks to the deployed Data Foundation over HTTP and
imports nothing from this repository's applications, so a partner can vendor or
install it without knowing how the service is built.

The tool surface follows CONTRACT.md v0.1.  Two rules from that document shape
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

DEFAULT_DATA_URL = "http://127.0.0.1:8860"


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

    # ------------------------------------------------------- tool 1: designs

    def list_designs(self) -> list[dict[str, Any]]:
        """Designs the service knows about, grouped client-side from snapshots.

        The service indexes immutable snapshots, not a design catalogue, so the
        grouping happens here until a design directory exists server-side.
        """
        grouped: dict[str, dict[str, Any]] = {}
        for snapshot in self._get(self.data_url, "/snapshots")["snapshots"]:
            design = grouped.setdefault(snapshot["design_id"], {
                "design_id": snapshot["design_id"],
                "revisions": {},
                "runs": set(),
                "snapshot_count": 0,
                "latest_snapshot_at": None,
            })
            design["revisions"][snapshot.get("revision_id")] = True
            design["runs"].add(snapshot.get("run_id"))
            design["snapshot_count"] += 1
            created = snapshot.get("created_at")
            if created and (design["latest_snapshot_at"] is None
                            or created > design["latest_snapshot_at"]):
                design["latest_snapshot_at"] = created
        return [{"design_id": item["design_id"],
                 "revisions": sorted(key for key in item["revisions"] if key),
                 "run_ids": sorted(key for key in item["runs"] if key),
                 "snapshot_count": item["snapshot_count"],
                 "latest_snapshot_at": item["latest_snapshot_at"]}
                for item in sorted(grouped.values(), key=lambda row: row["design_id"])]

    # ---------------------------------------------------------- tool 2: runs

    def list_runs(self, *, design_id: str | None = None, stage: str | None = None,
                  status: str | None = None, limit: int = 100,
                  offset: int = 0) -> list[dict[str, Any]]:
        """Execution runs, from the execution foundation.

        Needs ``kernel_url``.  ``stage`` and ``status`` filter client-side
        because the kernel indexes runs, not stages.
        """
        self._require_kernel("list_runs")
        rows = self._get(self.kernel_url, "/kernel/runs")["runs"]
        if design_id:
            rows = [row for row in rows if row.get("design_id") == design_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if stage:
            rows = [row for row in rows
                    if any(snapshot.get("stage") == stage
                           for snapshot in self.get_run_summary(row["run_id"])["snapshots"])]
        return rows[offset:offset + limit]

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
        rows = self._get(self.kernel_url, f"/kernel/runs/{_segment(run_id)}/artifacts")["artifacts"]
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        return rows

    # ------------------------------------------------------- tool 6: metrics

    def get_metrics(self, *, run_id: str | None = None, snapshot_id: str | None = None,
                    stage: str | None = None, name: str | None = None,
                    include_raw: bool = False, limit: int = 100,
                    offset: int = 0) -> dict[str, Any]:
        """Canonical metrics with their authoritative source.

        Scoping by ``snapshot_id`` resolves the owning run first and then keeps
        only the rows that carry that snapshot, so the canonical projection is
        the same one the run-scoped call uses.
        """
        if run_id is None:
            if snapshot_id is None:
                raise ValueError("get_metrics needs run_id or snapshot_id")
            run_id = self._get(self.data_url,
                               f"/snapshots/{_segment(snapshot_id)}")["snapshot"]["run_id"]
        params = {"stage": stage, "name": name, "limit": limit, "offset": offset}
        if include_raw:
            params["include_raw"] = 1
        result = self._get(self.data_url, f"/runs/{_segment(run_id)}/metrics",
                           {key: value for key, value in params.items() if value is not None})
        if snapshot_id is not None:
            result["metrics"] = [row for row in result.get("metrics", [])
                                 if row.get("snapshot_id") == snapshot_id]
            result["count"] = len(result["metrics"])
            result["returned"] = len(result["metrics"])
            result["snapshot_id"] = snapshot_id
        return result

    # -------------------------------------------------- tool 7: timing paths

    def get_timing_paths(self, snapshot_id: str, *, check: str | None = None,
                         limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Timing path summaries; ``check`` filters setup/hold client-side."""
        result = self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/timing-paths",
                           {"limit": limit, "offset": offset})
        if check:
            result["timing_paths"] = [row for row in result.get("timing_paths", [])
                                      if row.get("check") == check]
            result["returned"] = len(result["timing_paths"])
        return result

    # ------------------------------------------------ tool 8: one timing path

    def get_timing_path(self, snapshot_id: str, path_id: str,
                        *, include: str = "summary",
                        detail: str = "summary") -> dict[str, Any]:
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
        return self._get(self.data_url, f"{base}/context", {"detail": detail})

    # ----------------------------------------------------- tool 9: instances

    def get_instance(self, snapshot_id: str, name: str,
                     *, detail: str = "summary") -> dict[str, Any]:
        """One instance by exact name, with its physical facts and relations.

        Zero matches and several matches are distinct outcomes, not an
        exception and not "take the first one".
        """
        found = self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/instances",
                          {"name": name})["instances"]
        if len(found) != 1:
            return {"snapshot_id": snapshot_id, "name": name, "instances": found,
                    "status": "not_found" if not found else "partial",
                    "reason": ("no instance carries this exact name" if not found else
                               "more than one instance carries this exact name")}
        object_id = found[0]["object_id"]
        context = self._get(self.data_url,
                            f"/snapshots/{_segment(snapshot_id)}/objects/"
                            f"{_segment(object_id)}/context", {"detail": detail})
        return {"snapshot_id": snapshot_id, "name": name, "status": "available",
                "instance": context["entities"][0], "context": context,
                "physical_context": context.get("physical_context", []),
                "relations": context.get("relations", []),
                "evidence": context.get("evidence", [])}

    # --------------------------------------------------- tool 10: net context

    def get_net_context(self, snapshot_id: str, net: str,
                        *, detail: str = "summary") -> dict[str, Any]:
        """A net by object ID or exact name: connectivity, route and sources."""
        net_id = net
        if not net.startswith("net:"):
            found = self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/nets",
                              {"name": net})["nets"]
            if len(found) != 1:
                return {"snapshot_id": snapshot_id, "name": net, "nets": found,
                        "status": "not_found" if not found else "partial",
                        "reason": ("no net carries this exact name" if not found else
                                   "more than one net carries this exact name")}
            net_id = found[0]["object_id"]
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/nets/"
                         f"{_segment(net_id)}/context", {"detail": detail})

    # --------------------------------------------- tool 11: physical context

    def get_physical_context(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        """Location, bbox, geometry and routing for one object."""
        return self._get(self.data_url,
                         f"/snapshots/{_segment(snapshot_id)}/physical/{_segment(object_id)}")

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
        return self._get(self.data_url, f"/snapshots/{_segment(snapshot_id)}/evidence",
                         {"artifact_id": artifact_id, "limit": limit, "offset": offset})

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
        return json.loads(self._get_bytes(base, path, params))

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
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
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

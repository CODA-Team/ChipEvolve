"""Typed HTTP client for the kernel service."""

from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: How long a call may take.  Submitting a task is fast; reading a large
#: artifact excerpt is bounded server-side, so this only has to cover the
#: round trip and normal queuing.
DEFAULT_TIMEOUT_SECONDS = 30.0

#: The excerpt ceiling the kernel enforces.  Restated here so a caller gets an
#: immediate error instead of a 400 after a round trip.
MAX_EXCERPT_BYTES = 64 * 1024


class KernelError(RuntimeError):
    """The kernel refused the call, or answered something unexpected."""

    def __init__(self, message: str, *, status: int | None = None,
                 body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class KernelUnavailable(KernelError):
    """The kernel could not be reached at all."""


@dataclass
class KernelClient:
    """A transport connection to one kernel."""

    base_url: str
    token: str | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    _extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"base_url must be http(s): {self.base_url!r}")
        self.base_url = self.base_url.rstrip("/")

    # -- transport --------------------------------------------------------

    def _call(self, method: str, path: str, *,
              payload: Mapping[str, Any] | bytes | None = None,
              query: Mapping[str, Any] | None = None, want_bytes: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            cleaned = {
                k: v for k, v in query.items()
                if v is not None and v != "" and v != []
            }
            if cleaned:
                pairs: list[tuple[str, str]] = []
                for key, value in cleaned.items():
                    if isinstance(value, (list, tuple)):
                        pairs.extend((key, str(item)) for item in value)
                    else:
                        pairs.append((key, str(value)))
                url += "?" + urllib.parse.urlencode(pairs)

        headers = {"Accept": "application/json", **self._extra_headers}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body: bytes | None = None
        if payload is not None:
            if isinstance(payload, bytes):
                body = payload
                headers["Content-Type"] = "application/octet-stream"
            else:
                body = json.dumps(payload).encode("utf-8")
                headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers,
                                         method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise KernelError(
                _error_message(exc), status=exc.code, body=_safe_json(exc.read())
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise KernelUnavailable(
                f"kernel at {self.base_url} is unreachable: {exc}"
            ) from exc

        if not raw:
            return None
        if want_bytes:
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KernelError(
                f"kernel returned a non-JSON body for {method} {path}"
            ) from exc

    # -- identity ---------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self._call("GET", "/kernel/health")

    def plugins(self) -> list[dict[str, Any]]:
        return self._call("GET", "/kernel/plugins")["plugins"]

    def upload_input(self, content: bytes) -> dict[str, Any]:
        """Upload bytes that a later TaskSpec can reference by input_id."""
        if not isinstance(content, bytes):
            raise TypeError("input content must be bytes")
        return self._call("POST", "/kernel/inputs", payload=content)["input"]

    def upload_input_chunks(self, chunks: Sequence[bytes]) -> dict[str, Any]:
        """Upload a potentially large input without one oversized request."""
        upload_id = secrets.token_urlsafe(24)
        offset = 0
        result: dict[str, Any] | None = None
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, bytes):
                raise TypeError("input chunks must be bytes")
            result = self._call(
                "POST", "/kernel/inputs/chunk", payload=chunk,
                query={"upload_id": upload_id, "offset": offset,
                       "final": "1" if index == len(chunks) - 1 else None},
            )
            offset = int(result.get("offset", offset + len(chunk)))
        if result is None or "input" not in result:
            raise ValueError("at least one input chunk is required")
        return result["input"]

    # -- runs -------------------------------------------------------------

    def submit(self, task: Mapping[str, Any], *,
               idempotent: bool = False,
               idempotency_key: str | None = None,
               plugin_version: str | None = None) -> dict[str, Any]:
        """Submit a task, optionally deduplicated by task id or stable key."""
        task_payload = dict(task)
        if plugin_version is not None:
            existing_version = task_payload.get("plugin_version")
            if existing_version is not None and existing_version != plugin_version:
                raise ValueError(
                    "plugin_version argument conflicts with the task payload"
                )
            task_payload["plugin_version"] = plugin_version
        return self._call("POST", "/kernel/runs",
                          payload={"task": task_payload},
                          query={"idempotent": "1" if idempotent else None,
                                 "idempotency_key": idempotency_key})

    def runs(self, *, project_id: str | None = None, design_id: str | None = None,
             plugin_id: str | None = None, status: str | None = None,
             run_type: str | None = None, analysis_of_run_id: str | None = None,
             limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        return self._call("GET", "/kernel/runs", query={
            "project_id": project_id, "design_id": design_id,
            "plugin_id": plugin_id, "status": status, "limit": limit,
            "run_type": run_type, "analysis_of_run_id": analysis_of_run_id,
            "offset": offset,
        })["runs"]

    def run(self, run_id: str) -> dict[str, Any]:
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}")["run"]

    def design_tree(self, design_id: str, *, limit: int | None = None,
                    offset: int = 0) -> dict[str, Any]:
        return self._call("GET", f"/kernel/designs/{_seg(design_id)}/tree",
                          query={"limit": limit, "offset": offset})

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self._call("POST", f"/kernel/runs/{_seg(run_id)}/cancel")

    def retry(self, run_id: str, *, reason: str) -> dict[str, Any]:
        return self._call("POST", f"/kernel/runs/{_seg(run_id)}/retry",
                          payload={"reason": reason})

    def bundle(self, run_id: str) -> dict[str, Any]:
        """Create a local ZIP evidence artifact for a completed or attempted run."""
        return self._call("POST", f"/kernel/runs/{_seg(run_id)}/bundle")["bundle"]

    def metrics(self, run_id: str, *, complete_only: bool = False
                ) -> list[dict[str, Any]]:
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}/metrics",
                          query={"complete_only": "1" if complete_only else None}
                          )["metrics"]

    def artifacts(self, run_id: str, *, category: str | None = None,
                  format: str | None = None, stage: str | None = None) -> list[dict[str, Any]]:
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}/artifacts",
                          query={"category": category, "format": format, "stage": stage})["artifacts"]

    def timeline(self, run_id: str) -> list[dict[str, Any]]:
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}/timeline"
                          )["timeline"]

    def resources(self, run_id: str) -> dict[str, Any]:
        """Return the platform capacity, reservations, and attempt usage view."""
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}/resources")["resources"]

    def logs(self, run_id: str, *, offset: int = 0,
             max_bytes: int | None = None) -> dict[str, Any]:
        return self._call("GET", f"/kernel/runs/{_seg(run_id)}/logs",
                          query={"offset": offset, "max_bytes": max_bytes})["logs"]

    def artifact_excerpt(self, run_id: str, artifact_id: str, *,
                         offset: int = 0, max_bytes: int = 8192
                         ) -> dict[str, Any]:
        if not 0 < max_bytes <= MAX_EXCERPT_BYTES:
            # Fail here rather than making the caller discover the ceiling from
            # a 400 after a round trip.
            raise ValueError(
                f"max_bytes must be between 1 and {MAX_EXCERPT_BYTES}"
            )
        return self._call(
            "GET",
            f"/kernel/runs/{_seg(run_id)}/artifacts/{_seg(artifact_id)}/excerpt",
            query={"offset": offset, "max_bytes": max_bytes},
        )

    def artifact_bytes(self, run_id: str, artifact_id: str) -> bytes:
        """Download a complete registered artifact within the server limit."""
        return self._call(
            "GET",
            f"/kernel/runs/{_seg(run_id)}/artifacts/{_seg(artifact_id)}/download",
            want_bytes=True,
        )

    def artifact_chunk(self, run_id: str, artifact_id: str, *, offset: int = 0,
                       max_bytes: int = MAX_EXCERPT_BYTES) -> dict[str, Any]:
        if not 0 < max_bytes <= MAX_EXCERPT_BYTES:
            raise ValueError(f"max_bytes must be between 1 and {MAX_EXCERPT_BYTES}")
        return self._call(
            "GET", f"/kernel/runs/{_seg(run_id)}/artifacts/"
            f"{_seg(artifact_id)}/chunk",
            query={"offset": offset, "max_bytes": max_bytes},
        )

    def artifact_locator(self, run_id: str, artifact_id: str) -> dict[str, Any]:
        """Where this artifact's bytes already are, when the kernel is on this host.

        Same-host ingestion should open that path rather than pulling the bytes
        through the chunk loop: the kernel only answers with a path it has
        proven to be inside its own state root, and only for an artifact that
        belongs to ``run_id``.  Use :meth:`materialize_artifact` when the kernel
        may be remote.
        """
        return self._call(
            "GET",
            f"/kernel/runs/{_seg(run_id)}/artifacts/{_seg(artifact_id)}/locator",
        )["locator"]

    def materialize_artifact(self, run_id: str, artifact_id: str, destination: str,
                             *, chunk_size: int = MAX_EXCERPT_BYTES) -> dict[str, Any]:
        """Put an artifact's bytes at ``destination``, copying locally when possible.

        Same-host preferred: the bytes are copied from the path the kernel
        reports and hashed in the same pass, so the artifact is read once at
        disk speed instead of 64 KiB per round trip, and the copy still fails
        unless it matches the registered SHA-256.  A kernel on another host, or
        a path this host cannot see, falls back to the chunked
        :meth:`download_artifact_to`, which re-checks the hash itself.
        """
        try:
            locator = self.artifact_locator(run_id, artifact_id)
        except KernelError:
            # Any refusal to locate -- an older kernel, a remote kernel, bytes
            # that moved -- is answered by moving the bytes instead, which is
            # never less verified.  The exception is not swallowed: a real
            # failure resurfaces from the download below.
            locator = None
        source = locator.get("path") if locator else None
        if isinstance(source, str) and os.path.isfile(source):
            digest, size_bytes = _copy_and_hash(source, destination)
            if digest != locator["sha256"] or size_bytes != locator["size_bytes"]:
                os.unlink(destination)  # never leave bytes that are not the artifact
                raise KernelError(
                    f"local artifact {artifact_id} does not match its registered hash"
                )
            return {"path": destination, "size_bytes": size_bytes,
                    "sha256": digest, "source": "local"}
        return {
            **self.download_artifact_to(run_id, artifact_id, destination,
                                        chunk_size=chunk_size),
            "source": "download",
        }

    def download_artifact_to(self, run_id: str, artifact_id: str,
                             destination: str, *,
                             chunk_size: int = MAX_EXCERPT_BYTES) -> dict[str, Any]:
        """Fetch an artifact over HTTP, chunk by chunk, verifying SHA-256.

        Prefer :meth:`materialize_artifact` (or
        :class:`LocalFirstKernelClient`) for same-host ingestion: this loop
        reads at most ``chunk_size`` per round trip, so a large artifact costs
        thousands of requests to move bytes that may already be on this disk.
        """
        import base64
        import hashlib
        offset = 0
        digest = None
        hasher = hashlib.sha256()
        with open(destination, "wb") as output:
            while True:
                chunk = self.artifact_chunk(run_id, artifact_id, offset=offset,
                                            max_bytes=chunk_size)
                data = base64.b64decode(chunk["data_base64"])
                output.write(data)
                hasher.update(data)
                offset += len(data)
                digest = chunk["sha256"]
                if not chunk["truncated"]:
                    break
        measured = hasher.hexdigest()
        if digest != measured:
            raise KernelError("downloaded artifact failed SHA-256 verification")
        return {"path": destination, "size_bytes": offset, "sha256": measured}

    def graph(self, run_ids: Sequence[str]) -> dict[str, Any]:
        return self._call("GET", "/kernel/graph",
                          query={"run_id": list(run_ids)})["graph"]


class LocalFirstKernelClient(KernelClient):
    """A kernel client that moves artifact bytes by path when they are already here.

    ``bundle.load_run_bundle`` asks its client to *download* a bundle.  On the
    execution host that bundle is on the same disk, and the chunk loop turns one
    file copy into thousands of HTTP round trips.  Substituting this class where
    the client is constructed leaves every caller unchanged -- no signature, no
    call site, and the fallback still runs when the kernel is remote.
    """

    def download_artifact_to(self, run_id: str, artifact_id: str,
                             destination: str, *,
                             chunk_size: int = MAX_EXCERPT_BYTES) -> dict[str, Any]:
        # The returned dict carries one extra key ("source") saying which path
        # was taken; every documented key keeps its meaning.
        return self.materialize_artifact(run_id, artifact_id, destination,
                                         chunk_size=chunk_size)


def _seg(value: str) -> str:
    """Percent-encode one path segment.

    Ids are platform-generated and normally safe, but a client that builds paths
    by concatenation should not be the place where a traversal becomes possible.
    """
    return urllib.parse.quote(str(value), safe="")


def _copy_and_hash(source: str, destination: str) -> tuple[str, int]:
    """Copy a file while hashing it, so a large artifact is read exactly once."""
    import hashlib
    hasher = hashlib.sha256()
    size_bytes = 0
    with open(source, "rb") as origin, open(destination, "wb") as target:
        while True:
            block = origin.read(1024 * 1024)
            if not block:
                break
            target.write(block)
            hasher.update(block)
            size_bytes += len(block)
    return hasher.hexdigest(), size_bytes


def _error_message(exc: urllib.error.HTTPError) -> str:
    body = _safe_json(exc.read())
    if isinstance(body, Mapping) and body.get("error"):
        return str(body["error"])
    return f"kernel returned HTTP {exc.code}"


def _safe_json(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")[:500]

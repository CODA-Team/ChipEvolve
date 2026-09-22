"""Small read-only HTTP client for the execution-foundation public API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from typing import cast

from query_agent.domain.errors import RunEvidenceError


class HttpExecutionFoundationClient:
    """The GET-only public API surface required by run evidence mapping."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds

    def run(self, run_id: str) -> Mapping[str, object]:
        return _object(self._get(f"/kernel/runs/{_segment(run_id)}"), "run")

    def runs(
        self,
        *,
        project_id: str | None = None,
        design_id: str | None = None,
        plugin_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> Sequence[Mapping[str, object]]:
        payload = self._get(
            "/kernel/runs",
            {
                "project_id": project_id,
                "design_id": design_id,
                "plugin_id": plugin_id,
                "status": status,
                "limit": limit,
            },
        )
        return _objects(payload, "runs")

    def metrics(
        self, run_id: str, *, complete_only: bool = False
    ) -> Sequence[Mapping[str, object]]:
        payload = self._get(
            f"/kernel/runs/{_segment(run_id)}/metrics",
            {"complete_only": "1" if complete_only else None},
        )
        return _objects(payload, "metrics")

    def artifacts(
        self,
        run_id: str,
        *,
        category: str | None = None,
        format: str | None = None,
        stage: str | None = None,
    ) -> Sequence[Mapping[str, object]]:
        payload = self._get(
            f"/kernel/runs/{_segment(run_id)}/artifacts",
            {"category": category, "format": format, "stage": stage},
        )
        return _objects(payload, "artifacts")

    def logs(
        self, run_id: str, *, offset: int = 0, max_bytes: int | None = None
    ) -> Mapping[str, object]:
        payload = self._get(
            f"/kernel/runs/{_segment(run_id)}/logs",
            {"offset": offset, "max_bytes": max_bytes},
        )
        return _object(payload, "logs")

    def artifact_excerpt(
        self,
        run_id: str,
        artifact_id: str,
        *,
        offset: int = 0,
        max_bytes: int = 8192,
    ) -> Mapping[str, object]:
        return self._get(
            f"/kernel/runs/{_segment(run_id)}/artifacts/"
            f"{_segment(artifact_id)}/excerpt",
            {"offset": offset, "max_bytes": max_bytes},
        )

    def timeline(self, run_id: str) -> Sequence[Mapping[str, object]]:
        payload = self._get(f"/kernel/runs/{_segment(run_id)}/timeline")
        return _objects(payload, "timeline")

    def graph(self, run_ids: Sequence[str]) -> Mapping[str, object]:
        payload = self._get("/kernel/graph", {"run_id": tuple(run_ids)})
        return _object(payload, "graph")

    def _get(
        self, path: str, query: Mapping[str, object] | None = None
    ) -> Mapping[str, object]:
        url = f"{self._base_url}{path}"
        if query:
            pairs: list[tuple[str, str]] = []
            for key, value in query.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple)):
                    values = cast(Sequence[object], value)
                    pairs.extend((key, str(item)) for item in values)
                else:
                    pairs.append((key, str(value)))
            if pairs:
                url = f"{url}?{urllib.parse.urlencode(pairs)}"
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout_seconds
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RunEvidenceError(
                f"execution foundation returned HTTP {exc.code} for {path}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RunEvidenceError(
                f"execution foundation is unreachable at {self._base_url}"
            ) from exc
        try:
            decoded: object = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RunEvidenceError(
                "execution foundation returned invalid JSON"
            ) from exc
        if not isinstance(decoded, Mapping):
            raise RunEvidenceError("execution foundation response must be an object")
        return cast(Mapping[str, object], decoded)


def _segment(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _object(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise RunEvidenceError(f"execution foundation response needs object {key!r}")
    return cast(Mapping[str, object], value)


def _objects(payload: Mapping[str, object], key: str) -> Sequence[Mapping[str, object]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise RunEvidenceError(f"execution foundation response needs list {key!r}")
    values = cast(list[object], value)
    if not all(isinstance(item, Mapping) for item in values):
        raise RunEvidenceError(
            f"execution foundation response {key!r} must contain objects"
        )
    return tuple(cast(Mapping[str, object], item) for item in values)

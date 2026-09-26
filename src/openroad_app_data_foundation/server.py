"""HTTP boundary for deterministic design-data queries."""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from openroad_platform_client import KernelClient, KernelError, KernelUnavailable
from openroad_platform_contracts import ContractError

from .bundle import import_ready_bundles, load_run_bundle
from .context import timing_path_context
from .queries import list_timing_paths, path_points, timing_path
from .repository import DataStore


class Handler(BaseHTTPRequestHandler):
    server_version = "design-data-foundation/0.1"
    store: DataStore
    execution_client: KernelClient | None = None

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
            self._send(200, self._get(parsed.path, query))
        except (KeyError, ValueError, ContractError) as exc:
            self._send(404 if isinstance(exc, KeyError) else 400, {"error": str(exc)})
        except KernelUnavailable as exc:
            self._send(503, {"error": str(exc)})
        except KernelError as exc:
            self._send(exc.status or 502, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/snapshots/from-run":
                payload = self._read_body()
                run_id = payload.get("run_id")
                artifact_id = payload.get("artifact_id")
                if not isinstance(run_id, str) or not isinstance(artifact_id, str):
                    raise ValueError("run_id and artifact_id are required")
                if self.execution_client is None:
                    raise KernelUnavailable("execution service is not configured")
                self._send(201, self.store.register_import(
                    artifact_id, load_run_bundle(self.execution_client, run_id, artifact_id)))
                return
            if self.path != "/snapshots":
                self._send(404, {"error": "not found"})
                return
            self._send(201, self.store.register(self._read_body()))
        except (ValueError, ContractError) as exc:
            self._send(400, {"error": str(exc)})
        except KernelUnavailable as exc:
            self._send(503, {"error": str(exc)})
        except KernelError as exc:
            self._send(exc.status or 502, {"error": str(exc)})

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        if path == "/health":
            return {"app": "data_foundation", "status": "ok"}
        if self.execution_client is not None:
            import_ready_bundles(self.store, self.execution_client)
        if path == "/snapshots":
            return {"snapshots": self.store.snapshots(
                design_id=query.get("design_id"), run_id=query.get("run_id"))}
        if path.startswith("/runs/") and path.endswith("/summary"):
            run_id = urllib.parse.unquote(path[len("/runs/"):-len("/summary")]).strip("/")
            if not run_id:
                raise ValueError("run_id is required")
            return self.store.run_summary_for_run(run_id)
        if path.startswith("/snapshots/"):
            parts = [urllib.parse.unquote(item) for item in path.split("/") if item]
            if len(parts) == 2:
                return {"snapshot": self.store.snapshot(parts[1])}
            if len(parts) == 3 and parts[2] == "summary":
                return self.store.run_summary(parts[1])
            if len(parts) == 3 and parts[2] == "instances":
                name = query.get("name")
                if not name:
                    raise ValueError("name is required")
                return {"snapshot_id": parts[1],
                        "instances": self.store.find_instance(parts[1], name)}
            if len(parts) >= 4 and parts[2] == "timing-paths":
                snapshot_id, path_id = parts[1], parts[3]
                if len(parts) == 4:
                    return timing_path(self.store, snapshot_id, path_id)
                if len(parts) == 5 and parts[4] == "points":
                    return path_points(self.store, snapshot_id, path_id, query)
                if len(parts) == 5 and parts[4] == "context":
                    return timing_path_context(self.store, snapshot_id, path_id)
            if len(parts) == 3 and parts[2] == "timing-paths":
                return list_timing_paths(self.store, parts[1], query)
            if len(parts) == 3 and parts[2] == "evidence":
                return {"snapshot_id": parts[1], "evidence": self.store.evidence(
                    parts[1], query.get("artifact_id"))}
            if len(parts) == 6 and parts[2] == "records" and parts[5] == "evidence":
                return {"evidence": self.store.record_evidence(
                    parts[1], parts[3], parts[4])}
            if len(parts) == 4 and parts[2] == "objects":
                return self.store.object(parts[1], parts[3], expansion=query.get("expansion", "summary"))
            if len(parts) == 4 and parts[2] == "nets":
                return self.store.net(parts[1], parts[3])
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "expand":
                return self.store.expand_net(parts[1], parts[3])
            if len(parts) == 4 and parts[2] == "physical":
                return {"physical_context": self.store.physical(parts[1], parts[3])}
        raise KeyError("not found")

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 32 * 1024 * 1024:
            raise ValueError("request body must be a non-empty JSON object")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


def serve(*, host: str, port: int, store: DataStore,
          kernel_url: str | None = None, kernel_token: str | None = None) -> None:
    handler = type("BoundHandler", (Handler,), {
        "store": store,
        "execution_client": (KernelClient(kernel_url, token=kernel_token)
                              if kernel_url else None),
    })
    ThreadingHTTPServer((host, port), handler).serve_forever()

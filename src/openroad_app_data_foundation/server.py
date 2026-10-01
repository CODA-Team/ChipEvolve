"""HTTP boundary for deterministic design-data queries."""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from openroad_platform_client import (KernelClient, KernelError, KernelUnavailable,
                                      LocalFirstKernelClient)
from openroad_platform_contracts import ContractError

from .artifacts import (DEFAULT_NATIVE_ROOT, artifact_manifest, native_files,
                        violations)
from .bundle import import_ready_bundles, load_run_bundle
from .context import net_context, object_context, timing_path_context
from .metric_queries import compare_metric
from .discovery import list_objects, timing_context, routing_summary
from .parasitics import net_parasitics
from .timing_queries import submit_timing_query, timing_query_status
from .envelope import envelope, error_envelope
from .queries import (
    compare_timing_path,
    list_evidence,
    read_evidence,
    list_metrics_for_run,
    list_observations,
    list_timing_paths,
    list_timing_points,
    path_points,
    timing_path,
)
from . import source_fingerprint

#: Captured when this module is imported - i.e. from the source the process
#: actually loaded.  Computing it per request would hash whatever is on disk at
#: that moment, which always matches and therefore detects nothing.
STARTUP_FINGERPRINT = source_fingerprint()
from .connections import ReadPool
from .repository import DataStore


class Handler(BaseHTTPRequestHandler):
    server_version = "design-data-foundation/0.1"
    store: DataStore
    execution_client: KernelClient | None = None
    auto_import: bool = True
    #: The flow tree this run's own reports and results were written to.  Only
    #: used for facts no bundle carries; see artifacts.py.
    native_root: Path = DEFAULT_NATIVE_ROOT
    #: Writes still take a lock; reads do not, because each request thread reads
    #: through its own read-only connection (see connections.ReadPool).  The lock
    #: used to cover every request, which serialised readers: measured against the
    #: real ariane136 store, 8 concurrent clients got 1.12x the throughput of one
    #: and a 0.6 ms request waited 14.7 s behind a single net-context request.
    request_lock = threading.Lock()
    #: Per-thread read connections.  Set by ``serve``; absent in tests that bind a
    #: store directly, in which case reads fall back to that store.
    read_pool: "ReadPool | None" = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/health":
                payload = self._get(parsed.path, query)
            elif self.read_pool is not None:
                # One borrowed read-only connection for this request; no request
                # lock, so a slow query no longer blocks every other caller.
                with self.read_pool.connection() as store:
                    payload = self._get(parsed.path, query, store)
            else:
                payload = self._get(parsed.path, query)
            if parsed.path == "/health":
                self._send(200, payload)
                return
            self._send(200, envelope(parsed.path, query, payload))
        except KeyError as exc:
            # CONTRACT 2: a missing target is a status, not an HTTP-shaped error
            # string.  str(exc) on a KeyError adds quotes, which is how the old
            # body ended up as {"error": "'... not found'"}.
            message = exc.args[0] if exc.args else "not found"
            self._send(404, error_envelope(parsed.path, "not_found", str(message)))
        except (ValueError, ContractError) as exc:
            self._send(400, error_envelope(parsed.path, "unavailable", str(exc)))
        except KernelUnavailable as exc:
            self._send(503, error_envelope(parsed.path, "unavailable", str(exc)))
        except KernelError as exc:
            self._send(exc.status or 502,
                       error_envelope(parsed.path, "unavailable", str(exc)))

    def do_POST(self) -> None:  # noqa: N802
        try:
            parts = [urllib.parse.unquote(item) for item in self.path.split('/') if item]
            if len(parts) == 3 and parts[0] == 'snapshots' and parts[2] == 'timing-queries':
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                query = self._read_body()
                with self.request_lock:
                    payload = submit_timing_query(self.store, self.execution_client, parts[1], query)
                self._send(202, payload)
                return
            if self.path == "/query":
                requests = self._read_body().get("requests")
                if not isinstance(requests, list) or not 1 <= len(requests) <= 20 or not all(
                        isinstance(path, str) and path.startswith("/snapshots/") and
                        not urllib.parse.urlparse(path).netloc for path in requests):
                    raise ValueError("requests must contain 1 to 20 snapshot query paths")
                results = []
                with self.request_lock:
                    for path in requests:
                        parsed = urllib.parse.urlparse(path)
                        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
                        results.append(envelope(parsed.path, query, self._get(parsed.path, query)))
                self._send(200, {"results": results})
                return
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
        except KeyError as exc:
            self._send(404, error_envelope(self.path, "not_found", str(exc)))
        except (ValueError, ContractError) as exc:
            self._send(400, {"error": str(exc)})
        except KernelUnavailable as exc:
            self._send(503, {"error": str(exc)})
        except KernelError as exc:
            self._send(exc.status or 502, {"error": str(exc)})
        except Exception as exc:                         # noqa: BLE001 - last resort
            # An unexpected bug used to close the socket with no response at all,
            # which a caller cannot distinguish from a dead service.  Answer with
            # the error instead, and let the log keep the traceback.
            self._send(500, error_envelope(self.path, "unavailable",
                                           f"{type(exc).__name__}: {exc}"))

    def _get(self, path: str, query: dict[str, str],
             store: "DataStore | None" = None) -> dict[str, Any]:
        if path == "/health":
            return {"app": "data_foundation", "status": "ok",
                    "source_fingerprint": STARTUP_FINGERPRINT}
        store = store if store is not None else self.store
        if self.execution_client is not None and self.auto_import:
            # Importing is a write, so it uses the writable store, not the reader.
            import_ready_bundles(self.store, self.execution_client)
        if path.startswith('/timing-queries/'):
            if self.execution_client is None:
                raise KernelUnavailable('execution service is not configured')
            return timing_query_status(self.store, self.execution_client, path.split('/')[-1])
        if path == "/snapshots":
            return {"snapshots": store.snapshots(
                design_id=query.get("design_id"), run_id=query.get("run_id"))}
        if path.startswith("/runs/") and path.endswith("/summary"):
            run_id = urllib.parse.unquote(path[len("/runs/"):-len("/summary")]).strip("/")
            if not run_id:
                raise ValueError("run_id is required")
            return store.run_summary_for_run(run_id)
        if path.startswith("/runs/") and path.endswith("/metrics"):
            run_id = urllib.parse.unquote(path[len("/runs/"):-len("/metrics")]).strip("/")
            if not run_id:
                raise ValueError("run_id is required")
            return list_metrics_for_run(self.store, run_id, query)
        if path.startswith("/snapshots/"):
            parts = [urllib.parse.unquote(item) for item in path.split("/") if item]
            if len(parts) == 6 and parts[2] == "compare" and parts[4] == "timing-paths":
                return compare_timing_path(
                    self.store, parts[1], parts[3], parts[5], query.get("to_path_id"))
            if len(parts) == 5 and parts[2] == "compare" and parts[4] == "metrics":
                name = query.get("name")
                if not name:
                    raise ValueError("name is required")
                return compare_metric(self.store, parts[1], parts[3], name,
                                      query.get("scene"))
            if len(parts) == 5 and parts[2] == 'sources' and parts[4] == 'excerpt':
                snapshot = store.snapshot(parts[1])
                refs = [r for r in snapshot.get('source_artifacts', []) if r.get('artifact_id') == parts[3]]
                if len(refs) != 1:
                    raise KeyError('artifact is not attached to this snapshot')
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                ref = refs[0]
                result = self.execution_client.artifact_excerpt(ref['run_id'], parts[3],
                    offset=_int_param(query, 'offset', 0), max_bytes=_int_param(query, 'max_bytes', 8192))
                return {'snapshot_id': parts[1], 'source': ref, 'excerpt': result}
            if len(parts) == 3 and parts[2] == "objects":
                return list_objects(self.store, parts[1], query)
            if len(parts) == 3 and parts[2] == "timing-context":
                return timing_context(self.store, parts[1])
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "routing-summary":
                return routing_summary(self.store, parts[1], parts[3])
            # Facts no bundle carries, read from the flow's own tree: the SPEF
            # the run was timed with, the reports it wrote, and the producer
            # manifest naming artifacts the adapter never staged.
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "parasitics":
                return net_parasitics(store, self.execution_client, parts[1],
                                      parts[3], query)
            if len(parts) == 3 and parts[2] == "artifacts":
                return artifact_manifest(store, self.execution_client, parts[1], query)
            if len(parts) == 4 and parts[2] == "artifacts" and parts[3] == "files":
                return native_files(store, parts[1], query, self.native_root)
            if len(parts) == 3 and parts[2] == "violations":
                return violations(store, parts[1], query, self.native_root)
            if len(parts) == 2:
                return {"snapshot": store.snapshot(parts[1])}
            if len(parts) == 3 and parts[2] == "summary":
                return store.run_summary(parts[1])
            if len(parts) == 3 and parts[2] == "instances":
                name = query.get("name")
                if not name:
                    return list_objects(self.store, parts[1], {**query, "kind": "instance"})
                return {"snapshot_id": parts[1],
                        "instances": store.find_instance(parts[1], name)}
            if len(parts) == 3 and parts[2] == "nets":
                name = query.get("name")
                if not name:
                    return list_objects(self.store, parts[1], {**query, "kind": "net"})
                return {"snapshot_id": parts[1],
                        "nets": store.find_net(parts[1], name)}
            if len(parts) >= 4 and parts[2] == "timing-paths":
                snapshot_id, path_id = parts[1], parts[3]
                if len(parts) == 4:
                    return timing_path(self.store, snapshot_id, path_id)
                if len(parts) == 5 and parts[4] == "points":
                    return path_points(self.store, snapshot_id, path_id, query)
                if len(parts) == 5 and parts[4] == "context":
                    return timing_path_context(
                        self.store, snapshot_id, path_id,
                        query.get("detail", "summary"),
                        _int_param(query, "relation_limit", 200))
                if len(parts) == 5 and parts[4] == "expand":
                    return timing_path_context(self.store, snapshot_id, path_id)
            if len(parts) == 3 and parts[2] == "timing-paths":
                return list_timing_paths(self.store, parts[1], query)
            if len(parts) == 3 and parts[2] == "timing-points":
                return list_timing_points(self.store, parts[1], query)
            if len(parts) == 3 and parts[2] == "observations":
                return list_observations(self.store, parts[1], query)
            if len(parts) == 3 and parts[2] == "evidence":
                return list_evidence(self.store, parts[1], query)
            if len(parts) == 6 and parts[2] == "records" and parts[5] == "fragments":
                return read_evidence(self.store, parts[1], parts[3], parts[4])
            if len(parts) == 6 and parts[2] == "records" and parts[5] == "evidence":
                return {"evidence": store.record_evidence(
                    parts[1], parts[3], parts[4])}
            if len(parts) == 5 and parts[2] == "objects" and parts[4] == "context":
                return object_context(self.store, parts[1], parts[3],
                                      query.get("detail", "summary"),
                                      _int_param(query, "relation_limit", 200))
            if len(parts) == 4 and parts[2] == "objects":
                return store.object(parts[1], parts[3], expansion=query.get("expansion", "summary"))
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "context":
                return net_context(self.store, parts[1], parts[3],
                                   query.get("detail", "summary"),
                                   _int_param(query, "relation_limit", 200))
            if len(parts) == 4 and parts[2] == "nets":
                return store.net(parts[1], parts[3])
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "expand":
                return store.expand_net(parts[1], parts[3])
            if len(parts) == 4 and parts[2] == "physical":
                return {"physical_context": store.physical(parts[1], parts[3])}
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
          kernel_url: str | None = None, kernel_token: str | None = None,
          auto_import: bool = True,
          native_root: str | Path = DEFAULT_NATIVE_ROOT) -> None:
    handler = type("BoundHandler", (Handler,), {
        "store": store, "auto_import": auto_import,
        "native_root": Path(native_root),
        # A reader per request thread; the writable store above stays for imports.
        "read_pool": ReadPool(store.path) if hasattr(store, "path") else None,
        "execution_client": (LocalFirstKernelClient(kernel_url, token=kernel_token)
                              if kernel_url else None),
    })
    ThreadingHTTPServer((host, port), handler).serve_forever()


def _int_param(query: dict[str, str], name: str, default: int) -> int:
    """Read a bounded integer query parameter, refusing anything unparseable."""
    raw = query.get(name)
    if raw is None or raw == "":
        return default
    if not raw.lstrip("-").isdigit():
        raise ValueError(f"{name} must be an integer")
    return int(raw)

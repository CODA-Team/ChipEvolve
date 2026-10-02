"""HTTP boundary for deterministic design-data queries."""

from __future__ import annotations

import json
import threading
import urllib.parse
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from openroad_platform_client import (KernelClient, KernelError, KernelUnavailable,
                                      LocalFirstKernelClient)
from openroad_platform_contracts import ContractError

from .artifacts import (DEFAULT_NATIVE_ROOT, artifact_manifest, native_files,
                        violations, native_excerpt, run_inventory)
from .bundle import import_ready_bundles, load_run_bundle
from .context import net_context, object_context, timing_path_context
from .metric_queries import compare_metric
from .discovery import list_objects, timing_context, routing_summary
from .parasitics import net_parasitics
from .engineering import (object_statistics, path_engineering, timing_overview,
                          routing_totals, instance_engineering, net_engineering, compare_inventory)
from .constraints import constraint_context
from .resolved_timing import resolved_timing_overview
from .source_metadata import source_metadata
from .api_help import api_help
from .excerpts import excerpt_view
from .pin_geometry import pin_engineering
from .native_inventory import net_inventory
from .analysis_setup import analysis_setup
from .evidence import object_provenance
from .clock_paths import clock_paths
from .path_endpoints import path_endpoints
from .batch_reads import read_batch
from .source_search import search_source
from .native_queries import submit_native_query, native_query_result
from .timing_queries import submit_timing_query, timing_query_status
from .identity import snapshot_identity, is_query_snapshot
from .metadata import metadata_view, placement_geometry, recovery_path
from .envelope import envelope, error_envelope
from .queries import (
    compare_timing_path,
    list_evidence,
    read_evidence,
    list_metrics_for_run,
    list_observations,
    list_timing_paths,
    list_timing_points,
    path_nets,
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


def _routing_limit(query: dict[str, str]) -> int | None:
    """`routing_limit=0` means every shape; absent means the default page."""
    raw = query.get("routing_limit")
    if raw is None:
        return None
    value = int(raw)
    if value < 0:
        raise ValueError("routing_limit must be >= 0")
    return value


def _routing_offset(query: dict[str, str]) -> int:
    raw = query.get("routing_offset", "0")
    value = int(raw)
    if value < 0:
        raise ValueError("routing_offset must be >= 0")
    return value


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
            if len(parts) == 3 and parts[0] == 'snapshots' and parts[2] == 'native-queries':
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                query = self._read_body()
                payload = submit_native_query(self.store, self.execution_client, parts[1], query, self.native_root)
                self._send(200 if payload.get('status') in ('succeeded', 'failed', 'timed_out', 'cancelled', 'lost')
                           else 202, payload)
                return
            if len(parts) == 3 and parts[0] == 'snapshots' and parts[2] == 'timing-queries':
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                query = self._read_body()
                with self.request_lock:
                    payload = submit_timing_query(self.store, self.execution_client, parts[1], query)
                payload["name_check"] = _name_check(self.store, parts[1], query)
                self._send(202, payload)
                return
            if self.path == "/query":
                body = self._read_body()
                with (self.read_pool.connection() if self.read_pool is not None
                      else nullcontext(self.store)) as store:
                    result = read_batch(body, lambda path, query: self._get(path, query, store))
                self._send(200, result)
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
            # The fingerprint says which build is running; it does not say which file
            # that build opened.  A service restarted against the wrong path answers
            # every request perfectly from the wrong store, so the identity travels
            # with the health answer and a caller can refuse to use it.
            return {"app": "data_foundation", "status": "ok",
                    "source_fingerprint": STARTUP_FINGERPRINT,
                    "database": self.store.identity()}
        store = store if store is not None else self.store
        if self.execution_client is not None and self.auto_import:
            # Importing is a write, so it uses the writable store, not the reader.
            import_ready_bundles(self.store, self.execution_client)
        if path.startswith('/native-queries/'):
            if self.execution_client is None:
                raise KernelUnavailable('execution service is not configured')
            return native_query_result(self.execution_client, path.split('/')[-1], query)
        if path.startswith('/timing-queries/'):
            if self.execution_client is None:
                raise KernelUnavailable('execution service is not configured')
            return _timing_query_outcome(store, timing_query_status(
                self.store, self.execution_client, path.split('/')[-1], _int_param(query, 'wait_seconds', 0)))
        if path == "/snapshots":
            snapshots = store.snapshots(design_id=query.get("design_id"), run_id=query.get("run_id"))
            origin = query.get('origin', 'all')
            if origin not in ('all', 'flow', 'query'):
                raise ValueError('snapshot origin must be all|flow|query')
            if origin != 'all':
                snapshots = [s for s in snapshots if is_query_snapshot(s) == (origin == 'query')]
            if query.get("fields"):
                fields = query["fields"].split(",")
                allowed = {"snapshot_id", "design_id", "revision_id", "run_id", "stage", "created_at"}
                if not set(fields) <= allowed:
                    raise ValueError("unknown snapshot projection field")
                snapshots = [{key: row.get(key) for key in fields} for row in snapshots]
            return {"snapshots": snapshots}
        if path.startswith("/runs/") and path.endswith("/summary"):
            run_id = urllib.parse.unquote(path[len("/runs/"):-len("/summary")]).strip("/")
            if not run_id:
                raise ValueError("run_id is required")
            return store.run_summary_for_run(run_id)
        if path.startswith("/runs/") and path.endswith("/metrics"):
            run_id = urllib.parse.unquote(path[len("/runs/"):-len("/metrics")]).strip("/")
            if not run_id:
                raise ValueError("run_id is required")
            return list_metrics_for_run(store, run_id, query)
        if path.startswith("/snapshots/"):
            parts = [urllib.parse.unquote(item) for item in path.split("/") if item]
            if len(parts) == 6 and parts[2] == "compare" and parts[4] == "timing-paths":
                return compare_timing_path(
                    store, parts[1], parts[3], parts[5], query.get("to_path_id"))
            if len(parts) == 5 and parts[2] == "compare" and parts[4] == "metrics":
                name = query.get("name")
                if not name:
                    raise ValueError("name is required")
                return compare_metric(store, parts[1], parts[3], name,
                                      query.get("scene"))
            if len(parts) == 5 and parts[2] == 'compare' and parts[4] == 'inventory':
                return compare_inventory(store, parts[1], parts[3], query, self.native_root, self.execution_client)
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
                return {'snapshot_id': parts[1], 'source': ref, 'excerpt': excerpt_view(result, query)}
            if len(parts) == 3 and parts[2] == "objects":
                return list_objects(store, parts[1], query)
            if len(parts) == 4 and parts[2:4] == ['objects', 'statistics']:
                return object_statistics(store, parts[1], query)
            if len(parts) == 3 and parts[2] == 'net-inventory':
                if query:
                    raise ValueError('net-inventory covers all native nets and accepts no filters')
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                return net_inventory(store, self.execution_client, parts[1], self.native_root)
            if len(parts) == 3 and parts[2] == 'analysis-setup':
                if set(query) - {'fields', 'detail'}:
                    raise ValueError('analysis-setup accepts fields and detail')
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                payload = analysis_setup(store, self.execution_client, parts[1], self.native_root)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 3 and parts[2] == 'timing-overview':
                if query.get('resolve', '0') not in ('0', '1'):
                    raise ValueError('resolve must be 0|1')
                if query.get('resolve') == '1':
                    if self.execution_client is None:
                        raise KernelUnavailable('execution service is not configured')
                    payload = resolved_timing_overview(store, self.store, self.execution_client, parts[1], query)
                    if payload['query_execution']['status'] != 'succeeded':
                        return payload
                    recovery_query = {key: value for key, value in query.items()
                                      if key not in ('resolve', 'wait_seconds', 'endpoint_path_count')}
                    recovery_query['check'] = query.get('check', 'setup')
                    recovery = '/snapshots/' + payload['snapshot_id'] + '/timing-overview'
                    if not query.get('fields'):
                        return payload
                    try:
                        return metadata_view(payload, recovery_query, recovery)
                    except ValueError as exc:
                        route = recovery_path(recovery, recovery_query)
                        raise ValueError(str(exc) + '; native query ' + payload['query_execution']['run_id']
                                         + ' already succeeded; correct the fields on ' + route
                                         + ' to reuse its complete result without another submission') from exc
                payload = timing_overview(store, parts[1], query)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 3 and parts[2] == 'routing-totals':
                return routing_totals(store, parts[1])
            if len(parts) == 3 and parts[2] == 'run-inventory':
                payload = run_inventory(store, parts[1], self.native_root, stage=query.get('stage'),
                                        metric_names=tuple(query.get('metrics', '').split(',')) if query.get('metrics') else (),
                                        metric_contains=tuple(query.get('metric_name_contains', '').split(',')) if query.get('metric_name_contains') else ())
                if not query.get('fields') and query.get('detail') != 'full' and (query.get('metrics') or query.get('metric_name_contains')):
                    query = {**query, 'fields': 'run_id,stages.stage,stages.metric_reports'}
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 3 and parts[2] == 'help':
                return api_help(store, parts[1], query)
            if len(parts) == 3 and parts[2] == 'source-metadata':
                payload = source_metadata(store, parts[1], self.native_root)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 5 and parts[2] == 'timing-paths' and parts[4] == 'engineering':
                payload = path_engineering(store, parts[1], parts[3], query)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 5 and parts[2] == 'timing-paths' and parts[4] == 'clock-paths':
                payload = clock_paths(store, parts[1], parts[3])
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 5 and parts[2] == 'timing-paths' and parts[4] == 'endpoints':
                payload = path_endpoints(store, parts[1], parts[3])
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 5 and parts[2] == 'pins' and parts[4] == 'engineering':
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                return pin_engineering(store, self.execution_client, parts[1], parts[3], self.native_root)
            if len(parts) == 5 and parts[2] == 'instances' and parts[4] == 'engineering':
                return instance_engineering(store, parts[1], parts[3])
            if len(parts) == 5 and parts[2] in ('instances', 'nets', 'pins') and parts[4] == 'provenance':
                if query:
                    raise ValueError('object provenance accepts no query filters')
                kind = {'instances': 'instance', 'nets': 'net', 'pins': 'pin'}[parts[2]]
                return object_provenance(store, parts[1], parts[3], kind)
            if len(parts) == 5 and parts[2] == 'nets' and parts[4] == 'engineering':
                payload = net_engineering(store, parts[1], parts[3], query)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 3 and parts[2] == "timing-context":
                return metadata_view(timing_context(store, parts[1]), query, path)
            if len(parts) == 3 and parts[2] == 'constraints':
                if self.execution_client is None:
                    raise KernelUnavailable('execution service is not configured')
                payload = constraint_context(store, self.execution_client, parts[1], query)
                return metadata_view(payload, query, path) if query.get('fields') else payload
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "routing-summary":
                return routing_summary(store, parts[1], parts[3])
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
            if len(parts) == 5 and parts[2:5] == ['artifacts', 'files', 'excerpt']:
                return native_excerpt(store, parts[1], query, self.native_root)
            if len(parts) == 5 and parts[2:5] == ['artifacts', 'files', 'search']:
                return search_source(store, parts[1], query, self.native_root)
            if len(parts) == 3 and parts[2] == "violations":
                return violations(store, parts[1], query, self.native_root)
            if len(parts) == 2:
                return metadata_view({"snapshot": store.snapshot(parts[1])}, {'detail': 'full', **query}, path)
            if len(parts) == 3 and parts[2] == "summary":
                return metadata_view(store.run_summary(parts[1]), query, path)
            if len(parts) == 3 and parts[2] == "instances":
                name = query.get("name")
                if not name:
                    return list_objects(store, parts[1], {**query, "kind": "instance"})
                return {"snapshot_id": parts[1], "snapshot": snapshot_identity(store.snapshot(parts[1])),
                        "instances": store.find_instance(parts[1], name)}
            if len(parts) == 3 and parts[2] == "nets":
                name = query.get("name")
                if not name:
                    return list_objects(store, parts[1], {**query, "kind": "net"})
                return {"snapshot_id": parts[1], "snapshot": snapshot_identity(store.snapshot(parts[1])),
                        "nets": store.find_net(parts[1], name)}
            if len(parts) >= 4 and parts[2] == "timing-paths":
                snapshot_id, path_id = parts[1], parts[3]
                if len(parts) == 4:
                    payload = timing_path(store, snapshot_id, path_id)
                    return metadata_view(payload, query, path) if query.get('fields') else payload
                if len(parts) == 5 and parts[4] == "points":
                    return path_points(store, snapshot_id, path_id, query)
                if len(parts) == 5 and parts[4] == "nets":
                    return path_nets(store, snapshot_id, path_id, query)
                if len(parts) == 5 and parts[4] == "context":
                    return timing_path_context(
                        store, snapshot_id, path_id,
                        query.get("detail", "summary"),
                        _int_param(query, "relation_limit", 200))
                if len(parts) == 5 and parts[4] == "expand":
                    return timing_path_context(store, snapshot_id, path_id)
            if len(parts) == 3 and parts[2] == "timing-paths":
                return list_timing_paths(store, parts[1], query)
            if len(parts) == 3 and parts[2] == "timing-points":
                return list_timing_points(store, parts[1], query)
            if len(parts) == 3 and parts[2] == "observations":
                return list_observations(store, parts[1], query)
            if len(parts) == 3 and parts[2] == "evidence":
                return list_evidence(store, parts[1], query)
            if len(parts) == 6 and parts[2] == "records" and parts[5] == "fragments":
                return read_evidence(store, parts[1], parts[3], parts[4])
            if len(parts) == 6 and parts[2] == "records" and parts[5] == "evidence":
                return {"evidence": store.record_evidence(
                    parts[1], parts[3], parts[4])}
            if len(parts) == 5 and parts[2] == "objects" and parts[4] == "context":
                return object_context(store, parts[1], parts[3],
                                      query.get("detail", "summary"),
                                      _int_param(query, "relation_limit", 200))
            if len(parts) == 4 and parts[2] == "objects":
                return store.object(parts[1], parts[3], expansion=query.get("expansion", "summary"))
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "context":
                return net_context(store, parts[1], parts[3],
                                   query.get("detail", "summary"),
                                   _int_param(query, "relation_limit", 200))
            if len(parts) == 4 and parts[2] == "nets":
                return store.net(parts[1], parts[3])
            if len(parts) == 5 and parts[2] == "nets" and parts[4] == "expand":
                return store.expand_net(parts[1], parts[3])
            if len(parts) == 4 and parts[2] == "physical":
                physical = store.physical(parts[1], parts[3],
                                          routing_limit=_routing_limit(query),
                                          routing_offset=_routing_offset(query))
                if 'x' in physical and 'y' in physical:
                    entity = store.entities_by_ids(parts[1], [parts[3]])[0]
                    scale = store.snapshot(parts[1])['run_summary']['dbu_per_micron']
                    physical.update(placement_geometry(physical, scale,
                        (entity.get('attributes') or {}).get('orientation')))
                payload = {"snapshot_id": parts[1],
                           "snapshot": snapshot_identity(store.snapshot(parts[1])),
                           "physical_context": physical}
                if physical.get("routing_truncated"):
                    # The page is a bounded view, so the envelope has to say so.
                    # Reporting `available` for a 100-of-1970 routing list is the
                    # silent truncation this project keeps having to remove.
                    payload["truncated"] = True
                    payload["limitations"] = [{
                        "field": "physical_context.routing",
                        "status": "truncated",
                        "returned": physical.get("routing_returned"),
                        "total": physical.get("routing_total"),
                        "next_offset": physical.get("next_offset"),
                        "reason": "routing list is paged; pass routing_limit=0 for "
                                  "every shape, or use routing-summary for totals",
                    }]
                return payload
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
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode("utf-8")
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


def _name_check(store, snapshot_id: str, query: dict) -> dict:
    """Whether each requested timing name is an object of the snapshot it ran on."""
    checked = {}
    for key in ("from_pin", "to_pin"):
        name = query.get(key)
        if not name:
            continue
        found = {}
        for kind in ("pin", "instance", "net"):
            rows = store.entities_named(snapshot_id, kind, name)
            if rows:
                found[kind] = [row["object_id"] for row in rows[:5]]
        checked[key] = {"name": name, "exists": bool(found), "objects": found}
    return checked


def _timing_query_outcome(store, status: dict) -> dict:
    """Say what the snapshot a query produced actually contains.

    A directed STA query answers with a report set, not a census, so an empty
    result has two causes that the report alone cannot separate: the requested
    name does not exist, or it exists outside the set this query asked for.
    ``name_check`` on submission rules out the first; these counts state the
    second, instead of leaving a caller to read zero paths as "not found".
    """
    if status.get("status") != "succeeded":
        return status
    results = []
    for snapshot_id in status.get("snapshot_ids", []):
        summary = store.run_summary(snapshot_id)
        counts = summary["record_counts"]
        context = summary["run_summary"].get("timing_context") or {}
        paths = counts.get("timing_paths", 0)
        results.append({
            "snapshot_id": snapshot_id, "timing_path_count": paths,
            "timing_point_count": counts.get("timing_points", 0),
            "coverage_scope": context.get("coverage_scope"),
            "reason": None if paths else "no_path_in_requested_set",
            "timing_paths": f"/snapshots/{snapshot_id}/timing-paths",
        })
    return {**status, "results": results}


def _int_param(query: dict[str, str], name: str, default: int) -> int:
    """Read a bounded integer query parameter, refusing anything unparseable."""
    raw = query.get(name)
    if raw is None or raw == "":
        return default
    if not raw.lstrip("-").isdigit():
        raise ValueError(f"{name} must be an integer")
    return int(raw)

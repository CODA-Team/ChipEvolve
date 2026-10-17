"""Single-machine HTTP surface preserves lifecycle and evidence, without accounts."""

import hashlib
import http.client
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from openroad_platform_client import KernelClient, KernelError
from openroad_platform_gateway import Response, Router, build_router, make_handler
from openroad_platform_gateway.bootstrap import KernelPaths, build_kernel
from openroad_platform_gateway.router import LocalHTTPServer
from openroad_platform_runtime import RuntimeWorker

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local(tmp_path, request):
    kernel = build_kernel(
        KernelPaths.of(tmp_path / "state", ROOT / "plugins", ROOT / "admissions")
    )
    server = LocalHTTPServer(("127.0.0.1", 0), make_handler(build_router(kernel)))
    http_thread = threading.Thread(target=server.serve_forever)
    http_thread.start()
    stop = threading.Event()
    worker = RuntimeWorker(kernel.store, kernel.runtime, idle_seconds=0.02)
    worker_thread = threading.Thread(target=worker.serve_forever, args=(stop,))
    running = getattr(request, "param", True)
    if running:
        worker_thread.start()
    yield KernelClient(f"http://127.0.0.1:{server.server_port}"), kernel
    stop.set()
    if running:
        worker_thread.join(timeout=20)
    assert not worker_thread.is_alive()
    server.shutdown()
    server.server_close()
    http_thread.join()
    kernel.store.close()


def task(task_id="t1"):
    return {
        "schema_version": 3,
        "task_id": task_id,
        "project_id": "test",
        "design_id": "chip",
        "plugin_id": "example-reporter",
        "inputs": {"records": [1, 2, 3, 4]},
        "timeout_seconds": 30,
    }


def terminal(client, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        run = client.run(run_id)
        if run["status"] in ("succeeded", "failed", "cancelled", "timed_out", "lost"):
            return run
        time.sleep(0.03)
    raise AssertionError("run never reached a terminal state")


def test_full_batch_connections_survive_until_dispatch_starts():
    router = Router()
    router.get("/check", lambda request: Response.json({"ok": True}))
    connections = []
    with LocalHTTPServer(("127.0.0.1", 0), make_handler(router)) as server:
        thread = threading.Thread(target=server.serve_forever)
        try:
            # A brief dispatch delay must not discard the native 50-leaf burst.
            for _ in range(50):
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port, timeout=2
                )
                connections.append(connection)
                connection.connect()
            thread.start()
            for connection in connections:
                connection.request("GET", "/check", headers={"Connection": "close"})
                response = connection.getresponse()
                assert response.status == 200
                assert json.loads(response.read()) == {"ok": True}
        finally:
            for connection in connections:
                connection.close()
            if thread.ident is not None:
                server.shutdown()
                thread.join(timeout=10)
                assert not thread.is_alive()


@pytest.mark.parametrize("local", [False], indirect=True)
def test_fifty_clients_upload_all_stage_inputs_with_exact_hashes(local):
    client, _ = local
    barrier = threading.Barrier(50)

    def upload(slot):
        own = KernelClient(client.base_url)
        barrier.wait(timeout=10)
        results = []
        for name, size in (("profile", 7500), ("config", 1400), ("sdc", 500)):
            body = f"{slot}:{name}".encode().ljust(size, b" ")
            uploaded = own.upload_input(body)
            assert uploaded["sha256"] == hashlib.sha256(body).hexdigest()
            results.append(uploaded["input_id"])
        return results

    with ThreadPoolExecutor(max_workers=50) as pool:
        bundles = list(pool.map(upload, range(50)))
    assert len(bundles) == 50
    assert len({input_id for bundle in bundles for input_id in bundle}) == 150


def test_http_runs_progress_resources_artifacts_and_durable_store(local, tmp_path):
    client, kernel = local
    assert client.health()["status"] == "ok"
    run = client.submit(task(), idempotency_key="one")["run"]
    assert (
        client.submit(task(), idempotency_key="one")["run"]["run_id"] == run["run_id"]
    )
    detail = terminal(client, run["run_id"])
    assert detail["status"] == "succeeded"
    assert detail["stages"] and detail["stages"][0]["attempts"]
    artifacts = client.artifacts(run["run_id"])
    assert {row["kind"] for row in artifacts} == {"summary", "log"}
    filtered = client._call(
        "GET", f"/kernel/runs/{run['run_id']}/artifacts?kind=summary"
    )
    assert {row["kind"] for row in filtered["artifacts"]} == {"summary"}
    report = next(row for row in artifacts if row["kind"] == "summary")
    assert (
        client.artifact_excerpt(run["run_id"], report["artifact_id"])["sha256"]
        == report["sha256"]
    )
    assert client.resources(run["run_id"])
    assert kernel.store.list_events(run["run_id"])
    assert not (tmp_path / "state/identity.db").exists()
    assert (
        client.runs(design_id="chip", status="succeeded")[0]["run_id"] == run["run_id"]
    )


@pytest.mark.parametrize("local", [False], indirect=True)
def test_queued_cancel_and_invalid_input_have_real_outcomes(local):
    client, kernel = local
    # Stop execution before submission so cancellation tests the queued boundary.
    run = kernel.runtime.submit(
        __import__("openroad_platform_contracts").TaskSpec.from_dict(task("cancel"))
    )
    cancelled = client.cancel(run.run_id)["run"]
    RuntimeWorker(kernel.store, kernel.runtime).cycle()
    assert terminal(client, run.run_id)["status"] == "cancelled"
    assert cancelled["run_id"] == run.run_id
    with pytest.raises(KernelError) as error:
        client.submit({**task("invalid"), "plugin_id": "missing-plugin"})
    assert error.value.status == 400


def test_old_accounts_and_proxy_routes_are_removed(local):
    client, _ = local
    for route in ("/kernel/auth/session", "/apps", "/app/plan_executor/health"):
        with pytest.raises(KernelError) as error:
            client._call("GET", route)
        assert error.value.status == 404


def test_remote_bind_is_refused_and_worker_cli_needs_no_source_injection(tmp_path):
    base = [
        sys.executable,
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(tmp_path / "state"),
        "--plugins-root",
        str(ROOT / "plugins"),
        "--admissions-root",
        str(ROOT / "admissions"),
    ]
    result = subprocess.run(
        [*base, "--host", "0.0.0.0"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2 and "loopback" in result.stderr
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openroad_platform_gateway.worker",
            *base[3:],
            "--once",
            "--quiet",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["advanced"] == 0


def test_missing_run_is_404_even_for_empty_catalog_endpoints(local):
    client, _ = local
    for method in (client.metrics, client.artifacts, client.resources, client.timeline):
        with pytest.raises(KernelError) as error:
            method("absent-run")
        assert error.value.status == 404


def test_adapter_context_cannot_be_spoofed_by_environment_resolver(tmp_path):
    from openroad_platform_contracts import PluginManifest, TaskSpec
    from openroad_platform_runtime import RuntimeStore, WorkflowRuntime

    script = tmp_path / "adapter.py"
    script.write_text("""import argparse, json, os
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--request'); p.add_argument('--result'); a=p.parse_args()
Path('scope.json').write_text(json.dumps({key:os.environ[key] for key in ('EXECUTION_RUN_ID','EXECUTION_ATTEMPT_ID','EXECUTION_TASK_ID')}))
Path(a.result).write_text(json.dumps({'schema_version':3, 'status':'succeeded', 'exit_code':0, 'started_at':'2026-10-08T00:00:00Z', 'ended_at':'2026-10-08T00:00:01Z', 'artifacts':[{'kind':'scope','path':'scope.json'}]}))
""")
    manifest = PluginManifest(
        plugin_id="scope-test",
        plugin_version="1",
        adapter_entry=(sys.executable, str(script)),
        capabilities=("scope",),
        supported_arch=("x86_64", "aarch64"),
        artifact_rules=(),
    )

    class Resolver:
        def resolve(self, *args, **kwargs):
            return manifest

    store = RuntimeStore(tmp_path / "runtime.db")
    runtime = WorkflowRuntime(
        store,
        Resolver(),
        workspace_root=tmp_path / "workspaces",
        environment_resolver=lambda run: {"EXECUTION_RUN_ID": "spoofed"},
    )
    try:
        run = runtime.submit(
            TaskSpec(
                task_id="immutable-task",
                project_id="test",
                design_id="chip",
                plugin_id="scope-test",
            )
        )
        runtime.execute_once(run.run_id)
        attempt = runtime.describe(run.run_id)["stages"][0]["attempts"][0]
        content = json.loads((Path(attempt["workspace"]) / "scope.json").read_text())
        assert content == {
            "EXECUTION_RUN_ID": run.run_id,
            "EXECUTION_ATTEMPT_ID": attempt["attempt_id"],
            "EXECUTION_TASK_ID": "immutable-task",
        }
    finally:
        store.close()

"""Design Data Foundation end-to-end smoke."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_DIR / "src"
CONTRACTS_DIR = APP_DIR.parents[1] / "contracts" / "src"
CLIENT_DIR = APP_DIR.parents[1] / "core" / "client" / "src"
DEFAULT_PORT = 8860


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _call(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else _free_port()
    with tempfile.TemporaryDirectory() as directory:
        db = str(Path(directory) / "data.db")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(SRC_DIR), str(CONTRACTS_DIR), str(CLIENT_DIR)]
            + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "openroad_app_data_foundation",
             "--host", "127.0.0.1", "--port", str(port), "--db", db],
            cwd=str(APP_DIR), env=env,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    assert _call(f"http://127.0.0.1:{port}/health")["status"] == "ok"
                    break
                except (OSError, AssertionError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            snapshot = {
                "snapshot": {"snapshot_id": "snap-smoke", "design_id": "gcd",
                             "revision_id": "rev-1", "run_id": "run-1",
                             "stage": "route", "created_at": "2026-01-01T00:00:00Z"},
                "timing_paths": [{"path_id": "path-1", "snapshot_id": "snap-smoke",
                                  "analysis": "view", "check": "setup", "group": "clk",
                                  "startpoint": "u1/A", "endpoint": "u2/Z", "slack": -0.1}],
                "timing_points": [{"point_id": "point-1", "path_id": "path-1",
                                    "ordinal": 0, "pin_name": "u1/A", "object_id": "u1"}],
                "entities": [{"object_id": "u1", "snapshot_id": "snap-smoke",
                               "kind": "instance", "name": "u1"},
                              {"object_id": "n1", "snapshot_id": "snap-smoke",
                               "kind": "net", "name": "n1"}],
                "relations": [{"relation_id": "r1", "snapshot_id": "snap-smoke",
                                "subject_id": "u1", "predicate": "connected_to",
                                "object_id": "n1"}],
                "physical_context": [{"object_id": "u1", "snapshot_id": "snap-smoke",
                                       "instance_name": "u1", "x": 1, "y": 2}],
            }
            _call(f"http://127.0.0.1:{port}/snapshots", "POST", snapshot)
            paths = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/timing-paths")
            assert paths["timing_paths"][0]["path_id"] == "path-1"
            detail = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/timing-paths/path-1")
            assert detail["timing_points"][0]["pin_name"] == "u1/A"
            context = _call(
                f"http://127.0.0.1:{port}/snapshots/snap-smoke/timing-paths/path-1/context")
            assert context["target"]["type"] == "timing_path"
            assert context["physical_context"][0]["x"] == 1
            expanded_path = _call(
                f"http://127.0.0.1:{port}/snapshots/snap-smoke/timing-paths/path-1/expand")
            assert expanded_path["target"]["id"] == "path-1"
            summary = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/summary")
            assert summary["record_counts"]["stages"] == 0
            found = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/instances?name=u1")
            assert found["instances"][0]["object_id"] == "u1"
            found_net = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/nets?name=n1")
            assert found_net["nets"][0]["object_id"] == "n1"
            expanded = _call(f"http://127.0.0.1:{port}/snapshots/snap-smoke/nets/n1/expand")
            assert expanded["connected_entities"][0]["object_id"] == "u1"
            print("data_foundation smoke: ok")
            return 0
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())

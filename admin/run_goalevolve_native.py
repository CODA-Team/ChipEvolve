"""Bounded, recorded GoalEvolve reproduction steps, not a product harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from run_dplevolve_native import digest, now, write_json

CONTROL_ROOTS = (
    "goalevolve/",
    "config/codex.json",
    "experiments/",
    "scripts/",
    "toolchain/",
    "third_party/official_checker/",
    "Makefile",
    "pyproject.toml",
    "artifact_evaluation/_common.py",
    "artifact_evaluation/ae1/",
    "artifact_evaluation/ae2/",
    "artifact_evaluation/ae3/",
    "artifact_evaluation/verify_openroad_snapshot.py",
    "artifact_evaluation/release_manifest.json",
)


def process_table() -> dict[int, tuple[int, int, str]]:
    """Parent, group and start time, including native subprocess sessions."""
    rows = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if fields[0] != "Z":
            rows[int(entry.name)] = (int(fields[1]), int(fields[2]), fields[19])
    return rows


def stop_native_tree(process: subprocess.Popen[bytes]) -> None:
    """GoalEvolve's command runners and Codex create additional sessions."""
    table = process_table()
    descendants = {process.pid}
    while True:
        expanded = descendants | {
            pid for pid, row in table.items() if row[0] in descendants
        }
        if expanded == descendants:
            break
        descendants = expanded
    identities = {pid: table[pid][2] for pid in descendants if pid in table}
    for signum in (signal.SIGTERM, signal.SIGKILL):
        current = process_table()
        groups = {
            current[pid][1]
            for pid, start in identities.items()
            if pid in current and current[pid][2] == start
        }
        for group in groups:
            if group == os.getpgrp():
                raise RuntimeError(
                    "Native child unexpectedly shares the supervisor's group."
                )
            try:
                os.killpg(group, signum)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = process_table()
        if not any(
            pid in current and current[pid][2] == start
            for pid, start in identities.items()
        ):
            return
        time.sleep(0.05)
    raise RuntimeError("GoalEvolve step left live descendants after cancellation.")


def control_inventory(source: Path) -> dict[str, str]:
    """Freeze controls; native AE verifiers separately check large snapshots."""
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=source)
    files = {}
    for name in sorted(filter(None, names.decode().split("\0"))):
        if not any(name == root or name.startswith(root) for root in CONTROL_ROOTS):
            continue
        path = source / name
        files[name] = (
            hashlib.sha256(os.readlink(path).encode()).hexdigest()
            if path.is_symlink()
            else digest(path)
        )
    return files


def run_step(
    run_root: Path,
    step: str,
    command: list[str],
    *,
    timeout: float,
    cwd: Path | None = None,
) -> dict[str, Any]:
    if not command or timeout <= 0 or step in (".", "..") or Path(step).name != step:
        raise ValueError("Use a command, positive timeout and single step name.")
    config_path = run_root / "config.json"
    config = json.loads(config_path.read_text())
    source = Path(config["source"])
    before = control_inventory(source)
    frozen = run_root / "control-manifest.json"
    if frozen.exists():
        manifest = json.loads(frozen.read_text())
        if manifest["files"] != before or manifest["config_sha256"] != digest(
            config_path
        ):
            raise RuntimeError(
                "Frozen controls/config changed; retain the run and start a new one."
            )
    else:
        write_json(
            frozen,
            {
                "source": str(source),
                "files": before,
                "created_at": now(),
                "config_sha256": digest(config_path),
                "head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=source,
                    text=True,
                ).strip(),
            },
        )
    budget_path = run_root / "budget.json"
    if not budget_path.exists():
        write_json(
            budget_path,
            {
                "started_epoch": time.time(),
                "seconds": config["budget_seconds"],
            },
        )
    budget = json.loads(budget_path.read_text())
    remaining = budget["started_epoch"] + budget["seconds"] - time.time()
    if remaining <= 0:
        raise RuntimeError(
            "Total reproduction budget exhausted; preserve the experiment."
        )
    effective_timeout = min(timeout, remaining)
    step_dir = run_root / "steps" / step
    step_dir.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    env.update(config["environment"])
    local_bypass = ",".join(
        filter(
            None,
            (env.get("NO_PROXY", env.get("no_proxy", "")), "127.0.0.1", "localhost"),
        )
    )
    env["NO_PROXY"] = env["no_proxy"] = local_bypass
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(run_root / "pycache")
    env["PATH"] = os.pathsep.join(config["path_prefixes"] + [env["PATH"]])
    receipt: dict[str, Any] = {
        "step": step,
        "command": command,
        "cwd": str(cwd or source),
        "timeout_seconds": effective_timeout,
        "started_at": now(),
        "config_sha256": digest(config_path),
        "runner_sha256": digest(Path(__file__)),
        "status": "running",
        "unified_execution": False,
    }
    started = time.monotonic()
    process = None
    with (step_dir / "output.log").open("xb") as log:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd or source,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            receipt.update(pid=process.pid, session_id=process.pid)
            write_json(step_dir / "receipt.json", receipt)
            code = process.wait(timeout=effective_timeout)
            receipt.update(
                status="succeeded" if code == 0 else "failed", exit_code=code
            )
        except subprocess.TimeoutExpired:
            assert process is not None
            stop_native_tree(process)
            receipt.update(status="budget_exhausted", exit_code=process.returncode)
        except KeyboardInterrupt:
            if process is not None:
                stop_native_tree(process)
            receipt.update(status="interrupted")
        except OSError as error:
            receipt.update(status="launch_failed", error=str(error))
        finally:
            after = control_inventory(source)
            changed = sorted(
                name
                for name in before.keys() | after.keys()
                if before.get(name) != after.get(name)
            )
            receipt.update(
                finished_at=now(),
                elapsed_seconds=time.monotonic() - started,
                source_changed=changed,
                log_sha256=digest(step_dir / "output.log"),
            )
            if changed:
                receipt["status"] = "source_changed"
            write_json(step_dir / "receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    receipt = run_step(
        args.run_root.resolve(),
        args.step,
        command,
        timeout=args.timeout_seconds,
        cwd=args.cwd,
    )
    print(json.dumps(receipt, ensure_ascii=False))
    raise SystemExit(0 if receipt["status"] == "succeeded" else 1)


if __name__ == "__main__":
    main()

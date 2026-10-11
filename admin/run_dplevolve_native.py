"""Record bounded native DPLEvolve commands; this is a slice verification tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def source_inventory(root: Path) -> dict[str, str]:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return {
        name: digest(root / name) for name in sorted(names.decode().split("\0")) if name
    }


def session_groups(session_id: int) -> set[int]:
    groups = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if int(fields[3]) == session_id and fields[0] != "Z":
            groups.add(int(fields[2]))
    return groups


def stop_session(process: subprocess.Popen[bytes]) -> None:
    for signum in (signal.SIGTERM, signal.SIGKILL):
        for group in session_groups(process.pid):
            try:
                os.killpg(group, signum)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    deadline = time.monotonic() + 5
    while session_groups(process.pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    if session_groups(process.pid):
        raise RuntimeError("Native step left live processes in its dedicated session.")


def run_step(
    run_root: Path,
    step: str,
    command: list[str],
    *,
    timeout: float,
    cwd: Path | None = None,
) -> dict[str, Any]:
    config_path = run_root / "config.json"
    config = json.loads(config_path.read_text())
    source = Path(config["environment"]["DPL_EVOLVE_AGENT_ROOT"])
    before = source_inventory(source)
    manifest = run_root / "source-manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text())["files"] != before:
            raise RuntimeError(
                "Frozen control source changed; create a new run directory."
            )
    else:
        write_json(
            manifest,
            {
                "source": str(source),
                "head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=source, text=True
                ).strip(),
                "files": before,
                "created_at": now(),
            },
        )
    step_dir = run_root / "steps" / step
    step_dir.mkdir(parents=True, exist_ok=False)
    write_json(step_dir / "config.json", config)
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    env.update(config["environment"])
    env["PYTHONNOUSERSITE"] = "1"
    env["DPL_EVOLVE_SKIP_ENV_SH"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(run_root / "pycache")
    env["PATH"] = os.pathsep.join(config["path_prefixes"] + [env["PATH"]])
    effective_cwd = cwd or source
    receipt: dict[str, Any] = {
        "step": step,
        "command": command,
        "cwd": str(effective_cwd),
        "timeout_seconds": timeout,
        "config_sha256": digest(config_path),
        "runner_sha256": digest(Path(__file__)),
        "started_at": now(),
        "status": "running",
        "unified_execution": False,
    }
    started = time.monotonic()
    with (step_dir / "output.log").open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=effective_cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        receipt["pid"] = process.pid
        receipt["session_id"] = process.pid
        write_json(step_dir / "receipt.json", receipt)
        try:
            code = process.wait(timeout=timeout)
            receipt.update(
                status="succeeded" if code == 0 else "failed", exit_code=code
            )
        except subprocess.TimeoutExpired:
            stop_session(process)
            receipt.update(status="budget_exhausted", exit_code=process.returncode)
        except KeyboardInterrupt:
            stop_session(process)
            receipt.update(status="interrupted", exit_code=process.returncode)
        finally:
            after = source_inventory(source)
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
    if not command or args.timeout_seconds <= 0 or Path(args.step).name != args.step:
        parser.error("Use a command, a positive timeout and a single step name.")
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

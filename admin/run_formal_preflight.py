"""Run an explicitly selected frozen step through the existing business CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from eda_toolkits.objectives import require_same_conditions

from admin.freeze_formal_campaign import checked
from chip_evolve.config import Deployment, business_lock, read, write
from chip_evolve.environment import check_environment, reference

ROOT = Path(__file__).resolve().parents[1]


def run_step(manifest: Path, design_id: str, step_key: str) -> dict[str, Any]:
    campaign = checked(manifest)
    design = next(r for r in campaign["designs"] if r["design_id"] == design_id)
    step = next(r for r in campaign["steps"] if r["key"] == step_key)
    deployment = Deployment(Path(campaign["config"]["path"]))
    prefix = campaign["experiment_prefix"]
    key = prefix + "-" + step_key
    experiment = deployment.state / "experiments" / design_id / key
    folder = manifest.parent / "steps" / design_id / step_key
    folder.mkdir(parents=True, exist_ok=True)
    with business_lock(folder):
        source = (
            Path(design[step["input"]]["path"])
            if step["input"] in {"selected_source", "reference"}
            else deployment.state
            / "experiments"
            / design_id
            / (prefix + "-" + step["input"])
            / "result.json"
        )
        frame = read(source)
        require_same_conditions(read(design["reference"]["path"]), frame)
        check_environment(
            deployment,
            Path(design["environment"]["path"]),
            design_id,
            step["capability"],
            source,
            "legacy",
        )
        request = {
            "campaign_id": campaign["campaign_id"],
            "design_id": design_id,
            "step": step,
            "source": reference(source),
        }
        saved = folder / "dispatch.json"
        if saved.exists() and read(saved) != request:
            raise ValueError("Preflight step source or method changed on recovery")
        write(saved, request)
        receipt = folder / "receipt.json"
        if receipt.exists() and read(receipt)["status"] == "succeeded":
            prior = read(receipt)
            if reference(Path(prior["result"]["path"])) != prior["result"]:
                raise ValueError("Completed preflight result changed")
            return prior
        command = [
            deployment.value["client_python"],
            str(ROOT / "chip-evolve.py"),
            "--config",
            str(deployment.path),
        ]
        if experiment.exists():
            command += ["resume", "--design", design_id, "--key", key]
        else:
            command += [
                "run",
                "--design",
                design_id,
                "--capability",
                step["capability"],
                "--key",
                key,
                "--source",
                str(source),
                "--operation",
                step["operation"],
                "--seconds",
                str(step["seconds"]),
                "--rounds",
                str(step.get("rounds", 1)),
            ]
        attempt = len(list(folder.glob("attempt-*.json"))) + 1
        output, error = (
            folder / f"stdout-{attempt}.log",
            folder / f"stderr-{attempt}.log",
        )
        started = time.time()
        write(
            receipt,
            {
                "status": "running",
                "command": command,
                "attempt": attempt,
                "started_at": started,
            },
        )
        with output.open("x") as stdout, error.open("x") as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
        state = (
            "succeeded"
            if process.returncode == 0
            else "pending"
            if process.returncode == 3
            else "failed"
        )
        value = {
            "campaign_id": campaign["campaign_id"],
            "design_id": design_id,
            "step": step_key,
            "status": state,
            "returncode": process.returncode,
            "attempt": attempt,
            "command": command,
            "started_at": started,
            "ended_at": time.time(),
            "wall_seconds": time.time() - started,
            "stdout": str(output),
            "stderr": str(error),
            "result": reference(experiment / "result.json")
            if state == "succeeded"
            else None,
            "native_search_restarted": False,
        }
        write(folder / f"attempt-{attempt}.json", value)
        write(receipt, value)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--step", required=True)
    args = parser.parse_args()
    value = run_step(args.manifest.resolve(), args.design, args.step)
    print(json.dumps(value))
    return (
        0
        if value["status"] == "succeeded"
        else 3
        if value["status"] == "pending"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())

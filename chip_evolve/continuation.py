"""One original Goal round from a verified power-complete source parent."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from chip_evolve.config import Deployment, business_lock, read, write
from chip_evolve.jobs import digest
from chip_evolve.native import latest_producer
from chip_evolve.professional import environment, freeze, inventory, invoke


def continuation_contract(
    original: dict[str, Any],
    parent: dict[str, Any],
    state: Path,
    source: Path,
    checkpoint: Path,
) -> dict[str, Any]:
    if not all(
        parent["metrics"][k] <= original["target_metrics"][k]
        for k in ["dynamic_power_pw", "leakage_power_pw"]
    ):
        raise ValueError("The original power targets are not complete")
    return {
        **original,
        "state_root": str(state),
        "max_campaign_rounds": 1,
        "initial_parent_id": "a7-imported-power-complete-parent",
        "initial_parent_source_root": str(source),
        "initial_parent_metrics": parent["metrics"],
        "initial_parent_source_commit": parent["source_commit"],
        "initial_parent_source_hash": parent["source_hash"],
        "initial_parent_evaluation_mode": parent["evaluation_mode"],
        "initial_parent_artifacts": {"checkpoint_post_route_db": str(checkpoint)},
    }


def checkpoint_producer(
    previous: Path,
    experiment: Path,
    checkpoint: Path,
    imported_parent: dict[str, Any],
    final_parent: dict[str, Any],
    previous_result: dict[str, Any],
) -> str:
    """Trace unchanged imported output through its original EF capture."""
    inherited = (
        final_parent["source_hash"] == imported_parent["source_hash"]
        and digest(checkpoint) == previous_result["qualification"]["input_odb_sha256"]
    )
    operations = (previous if inherited else experiment) / "operations"
    return latest_producer(
        operations, checkpoint, previous_result["qualification"]["producer_run_id"]
    )


def checkpoint_method(
    previous: Path,
    experiment: Path,
    producer: str,
    checkpoint: Path,
    parent: dict[str, Any],
) -> dict[str, Any]:
    """Describe the selected measured output separately from lineage metrics."""
    for root in (experiment, previous):
        for execution in (root / "operations").glob("*/execution.json"):
            if read(execution)["run"]["run_id"] != producer:
                continue
            request = execution.parent / "request.json"
            baseline = Path(read(request)["cwd"]) / "baseline.json"
            method = read(baseline) if baseline.is_file() else parent
            if method["source_hash"] != parent["source_hash"]:
                raise ValueError(
                    "Selected checkpoint source differs from native lineage"
                )
            if baseline.is_file() and digest(
                Path(method["artifacts"]["checkpoint_post_route_db"])
            ) != digest(checkpoint):
                raise ValueError("Selected baseline does not own the checkpoint bytes")
            return {
                **{
                    key: method[key]
                    for key in (
                        "source_hash",
                        "evaluation_mode",
                        "timing_recipe_id",
                        "metrics",
                    )
                },
                "producer_run_id": producer,
                "checkpoint_sha256": digest(checkpoint),
                "operation_request": str(request),
                "baseline_metadata": str(baseline) if baseline.is_file() else None,
            }
    raise ValueError("Selected checkpoint has no recorded EF operation")


def run(
    deployment: Deployment, previous: Path, context: Path, key: str, seconds: int
) -> dict[str, Any]:
    previous = previous.resolve()
    frame, parent = (
        read(previous / "result.json"),
        read(previous / "campaign/parent.json"),
    )
    original = read(previous / "evolve-config.json")
    parent_root = previous / "campaign/parents" / parent["source_hash"]
    checkpoint = parent_root / "design_checkpoint.odb"
    if digest(checkpoint) != frame["qualification"]["input_odb_sha256"]:
        raise ValueError("Imported parent checkpoint differs from its qualified result")
    experiment = deployment.experiment(frame["design_id"], key)
    with business_lock(experiment):
        controller = experiment / "controller"
        freeze(
            Path(deployment.value["professional"]["goal"]["source"]),
            controller,
            paths=[
                "goalevolve",
                "config",
                "experiments",
                "toolchain",
                "knowledge",
                "scripts",
                "pyproject.toml",
                "README.md",
            ],
        )
        shutil.copytree(
            previous / "controller/third_party/official_checker",
            controller / "third_party/official_checker",
        )
        profile = read(previous / "profile.json")
        profile_path = experiment / "profile.json"
        profile.update(
            profile_path=str(profile_path),
            state_root=str(experiment),
            agent_root=str(controller),
            experiment_id=frame["design_id"] + "-" + key,
            kernel_url=deployment.value["kernel_url"],
            client_python=deployment.value["client_python"],
            agent_python=deployment.value["goal_python"],
            operations_root=str(experiment / "operations"),
            deadline_epoch=time.time() + seconds,
            read_roots=[
                str(controller),
                profile["source_seed"],
                original.get("build_seed_root") or profile["source_seed"],
                str(previous / "inputs"),
                str(parent_root / "source"),
            ],
            write_roots=[str(experiment)],
            controller_files=inventory(controller),
        )
        write(profile_path, profile)
        config = continuation_contract(
            original,
            parent,
            experiment / "campaign",
            parent_root / "source",
            checkpoint,
        )
        config_path = experiment / "evolve-config.json"
        write(config_path, config)
        write(
            experiment / "input-receipt.json",
            {
                "source_result": str(previous / "result.json"),
                "original_contract": str(previous / "evolve-config.json"),
                "source_parent": parent,
                "checkpoint_sha256": digest(checkpoint),
                "context": str(context.resolve()),
                "unchanged_fields": [
                    "baseline_metrics",
                    "target_metrics",
                    "metric_weights",
                    "hard_metrics",
                    "promotion",
                    "power_stage_tns_ceiling_ns",
                    "power_stage_protected_rounds",
                ],
                "requested_rounds": 1,
                "students": config["students"],
                "budget_seconds": seconds,
                "input_role": "same frozen original benchmark; current validated source-parent output supplied as diagnostic context",
            },
        )
        from eda_toolkits.context import load_context

        packet = load_context(context.resolve())
        if (packet["scope"]["design_id"], packet["scope"]["run_id"]) != (
            frame["design_id"],
            frame["run_id"],
        ):
            raise ValueError("Continuation context belongs to another source run")
        write(
            experiment / "request.json",
            {
                "design": frame["design_id"],
                "capability": "goal-continuation",
                "source": str(previous / "result.json"),
                "seconds": seconds,
            },
        )
        env = environment(Path(frame["objective"]), context.resolve())
        env["GOALEVOLVE_PLATFORM_PROFILE"] = str(profile_path)
        folder = experiment / "evolve-controller"
        folder.mkdir()
        invoke(
            [
                profile["agent_python"],
                "-m",
                "goalevolve.cli",
                "run",
                "--config",
                str(config_path),
                "--rounds",
                "1",
                "--repository-graph",
                "on",
            ],
            controller,
            env,
            folder,
            seconds,
        )
        final_parent = read(experiment / "campaign/parent.json")
        odb = (
            experiment
            / "campaign/parents"
            / final_parent["source_hash"]
            / "design_checkpoint.odb"
        )
        producer = checkpoint_producer(
            previous, experiment, odb, parent, final_parent, frame
        )
        from chip_evolve.delivery import checkpoint as save_checkpoint
        from chip_evolve.delivery import finish

        method = {
            "kind": "native-timing-continuation",
            "imported_parent": parent,
            "parent": final_parent,
            "original_contract": str(previous / "evolve-config.json"),
            "selected_checkpoint": checkpoint_method(
                previous, experiment, producer, odb, final_parent
            ),
        }
        save_checkpoint(
            experiment,
            design_id=frame["design_id"],
            odb=odb,
            producer=producer,
            objective=Path(frame["objective"]),
            pdk=previous / "inputs/asap7",
            native_method=method,
        )
        result = finish(deployment, experiment)
        write(experiment / "status.json", {"status": "succeeded"})
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--seconds", type=int, default=21600)
    args = parser.parse_args()
    result = run(
        Deployment(args.config), args.previous, args.context, args.key, args.seconds
    )
    print(json.dumps({"run_id": result["run_id"], "metrics": result["metrics"]}))


if __name__ == "__main__":
    main()

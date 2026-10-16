"""Matched conversion/placement/routing control, separate from native algorithms."""

from __future__ import annotations

import argparse
from pathlib import Path

from chip_evolve.config import Deployment, read, write
from chip_evolve.delivery import checkpoint, finish
from chip_evolve.environment import reference
from chip_evolve.jobs import Jobs, digest
from chip_evolve.physical import container


def without_repairs(text: str) -> tuple[str, list[str]]:
    lines, removed = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("repair_design", "repair_timing", "repair_power")):
            if stripped.endswith("\\") or "{" in stripped or ";" in stripped:
                raise ValueError(
                    "Control requires explicit single-line native repair commands"
                )
            removed.append(line)
        else:
            lines.append(line)
    if not any(
        line.strip().startswith(("repair_power ", "repair_timing ")) for line in removed
    ):
        raise ValueError("This control needs an actual original power/timing repair")
    return "\n".join(lines) + "\n", removed


def run(deployment: Deployment, result: Path, key: str) -> dict:
    frame = read(result)
    if frame["native_method"]["kind"] not in {"native-fixed-source", "native-baseline"}:
        raise ValueError("Choose the completed Goal baseline or fixed-source replay")
    folder = deployment.state / "experiments" / frame["design_id"] / key
    request = {
        "result": reference(result),
        "method": "same Tcl/binary/input; omit native repair calls only",
    }
    if not folder.exists():
        folder = deployment.experiment(frame["design_id"], key)
        write(folder / "control-request.json", request)
    elif read(folder / "control-request.json") != request:
        raise ValueError("Control input changed on resume")
    if (folder / "result.json").exists():
        return read(folder / "result.json")
    if (folder / "delivery-checkpoint.json").exists():
        return finish(deployment, folder)
    original = result.parent / "baseline"
    baseline = read(original / "baseline.json")
    binary = Path(baseline["checks"][0]["detail"])
    build = binary.parent / "platform-build.json"
    binary_hash = digest(binary)
    if read(build)["binary_sha256"] != binary_hash:
        raise ValueError("Native control binary changed")
    output = folder / "native"
    output.mkdir(exist_ok=True)
    original_script = original / "evaluate.tcl"
    script = output / "evaluate.tcl"
    text, removed = without_repairs(original_script.read_text())
    script.write_text(text.replace(str(original), str(output)))
    write(
        folder / "control-method.json",
        {
            **request,
            "binary": reference(binary),
            "build_receipt": reference(build),
            "original_script": reference(original_script),
            "control_script": reference(script),
            "removed_commands": removed,
            "note": "An experimental ablation; never overwrite or describe it as the original professional method",
        },
    )
    jobs = Jobs(deployment, frame["design_id"], folder)
    source = read(result.parent / "input-receipt.json")["source"]
    record = jobs.command(
        "native-control",
        container(deployment, [str(binary), "-exit", str(script)]),
        capture=[
            script,
            folder / "control-method.json",
            output / "post_route.odb",
            output / "post_route.v",
        ],
        parent=read(source)["run_id"],
        objective=Path(frame["objective"]),
        seconds=1800,
        cpu=8,
        memory_gib=24,
    )
    jobs.log(record, output / "evaluation.log")
    if digest(binary) != binary_hash:
        raise ValueError("Native binary changed during the control")
    checkpoint(
        folder,
        design_id=frame["design_id"],
        odb=output / "post_route.odb",
        producer=record["run"]["run_id"],
        objective=Path(frame["objective"]),
        pdk=result.parent / "inputs/asap7",
        native_method={
            "kind": "conversion-routing-control",
            "source_run_id": read(source)["run_id"],
            "original_goal_result": str(result),
            "removed_commands": removed,
        },
    )
    return finish(deployment, folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    value = run(Deployment(args.config), args.result.resolve(), args.key)
    print(value["run_id"])


if __name__ == "__main__":
    main()

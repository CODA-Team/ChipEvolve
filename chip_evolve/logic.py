"""Fixed-Liberty output equivalence through EF, retaining physical-cell evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .comparisons import compare, proven_points
from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import container


def interface_and_physical(model: dict[str, Any], top: str) -> dict[str, Any]:
    module = model["modules"][top]
    ports = {
        name: {"direction": row["direction"], "width": len(row["bits"])}
        for name, row in module["ports"].items()
    }
    if not any(p["direction"] == "output" and p["width"] for p in ports.values()):
        raise ValueError("Proof requires nonempty top-level outputs")
    physical: set[str] = set()
    for cell in module["cells"].values():
        kind = cell["type"]
        if kind == "$scopeinfo" or re.match(r"^(TAPCELL|FILLER|DECAP)", kind):
            if cell["connections"]:
                raise ValueError("Cannot exclude a physical cell with port connections")
            physical.add(kind)
    return {"ports": ports, "zero_port_types": sorted(physical)}


def verify_outputs(
    deployment: Deployment, reference_path: Path, candidate_path: Path, experiment: Path
) -> dict[str, Any]:
    reference, candidate = read(reference_path), read(candidate_path)
    compare(reference, candidate)
    design = deployment.design(candidate["design_id"])
    libraries = [Path(row["path"]) for row in design["libraries"]]
    for path, row in zip(libraries, design["libraries"], strict=True):
        if digest(path) != row["sha256"]:
            raise ValueError("Declared Liberty logic model changed")
    experiment.mkdir(parents=True, exist_ok=True)
    jobs = Jobs(deployment, candidate["design_id"], experiment)
    checks, lines = [], []
    for frame, name in ((reference, "gold"), (candidate, "gate")):
        source = Path(frame["files"]["v"])
        parsed, script = experiment / (name + ".json"), experiment / (name + ".ys")
        script.write_text(
            f'read_verilog "{source}"\nhierarchy -top {design["top"]}\n'
            f'proc\nwrite_json "{parsed}"\n'
        )
        jobs.command(
            "parse-" + name,
            container(
                deployment, [deployment.value["tools"]["yosys"], "-s", str(script)]
            ),
            capture=[source, script, parsed],
            seconds=600,
            cpu=2,
            memory_gib=8,
            parent=candidate["run_id"],
            objective=Path(candidate["objective"]),
        )
        checked = interface_and_physical(read(parsed), design["top"])
        checks.append({"side": name, "parsed_sha256": digest(parsed), **checked})
        lines += [
            f'read_liberty -ignore_miss_func -ignore_miss_dir "{p}"' for p in libraries
        ]
        lines += [
            f'read_verilog "{source}"',
            "hierarchy -top " + design["top"],
            "proc",
            "flatten",
        ]
        lines += ["delete t:" + kind for kind in checked["zero_port_types"]]
        lines += [
            "rename -hide",
            "rename " + design["top"] + " " + name,
            "design -stash " + name,
        ]
    if checks[0]["ports"] != checks[1]["ports"]:
        raise ValueError("Proof top-level port interfaces differ")
    evidence = experiment / "model-evidence.json"
    write(evidence, checks)
    lines += [
        "design -reset",
        "design -copy-from gold -as gold gold",
        "design -copy-from gate -as gate gate",
        "equiv_make gold gate equiv",
        "hierarchy -top equiv",
        "equiv_simple",
        "equiv_induct -seq 5",
        "equiv_status -assert",
    ]
    script = experiment / "equivalence.ys"
    script.write_text("\n".join(lines) + "\n")
    engine = deployment.value["tools"].get("equivalence", "yosys")
    if engine not in {"yosys", "eqy"}:
        raise ValueError("Unknown equivalence backend: " + engine)
    if engine == "eqy":
        from .eqy import verify

        record, details = verify(jobs, reference, candidate, libraries, checks)
    else:
        record, details = _yosys_proof(jobs, candidate, reference, script, evidence)
    receipt = {
        "run_id": record["run"]["run_id"],
        "reference_result": str(reference_path),
        "candidate_result": str(candidate_path),
        **details,
        "unproven_points": 0,
        "top_output_bits": sum(
            p["width"]
            for p in checks[0]["ports"].values()
            if p["direction"] == "output"
        ),
        "input_hashes": {
            str(p): digest(p)
            for p in [
                *libraries,
                Path(reference["files"]["v"]),
                Path(candidate["files"]["v"]),
            ]
        },
        "model_checks": checks,
        "scope": "all top-level digital outputs under fixed Liberty and sequential induction; physical checks separate",
    }
    write(experiment / "logical-equivalence.json", receipt)
    return receipt


def _yosys_proof(
    jobs: Jobs,
    candidate: dict[str, Any],
    reference: dict[str, Any],
    script: Path,
    evidence: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = jobs.command(
        "logic",
        container(
            jobs.deployment,
            [jobs.deployment.value["tools"]["yosys"], "-s", str(script)],
        ),
        capture=[
            script,
            evidence,
            Path(reference["files"]["v"]),
            Path(candidate["files"]["v"]),
        ],
        seconds=jobs.deployment.value.get("validation", {}).get(
            "equivalence_seconds", 3600
        ),
        cpu=4,
        memory_gib=jobs.deployment.value.get("validation", {}).get(
            "equivalence_memory_gib", 32
        ),
        parent=candidate["run_id"],
        objective=Path(candidate["objective"]),
    )
    points = proven_points(jobs.log(record, jobs.experiment / "proof.log"))
    return record, {"engine": "yosys", "proven_points": points}

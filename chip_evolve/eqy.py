"""Existing EQY partitioned proof under the same fixed Liberty models and EF."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from .config import read
from .jobs import Jobs, digest
from .physical import container


def common_flop_states(
    gold: dict[str, Any], gate: dict[str, Any], top: str
) -> set[str]:
    """Proposed cut points; EQY must still prove every corresponding state."""
    left, right = gold["modules"], gate["modules"]
    common = {
        name: cell["type"]
        for name, cell in left[top]["cells"].items()
        if right[top]["cells"].get(name, {}).get("type") == cell["type"]
    }
    by_master: dict[str, set[str]] = {}
    for master in set(common.values()):
        model = left.get(master)
        if model is None or model != right.get(master):
            continue
        states = set()
        for cell in model.get("cells", {}).values():
            if not cell["type"].startswith("$_DFF"):
                continue
            bits = cell["connections"]["Q"]
            aliases = [
                name
                for name, wire in model["netnames"].items()
                if wire["bits"] == bits and not wire.get("hide_name")
            ]
            if aliases:
                states.add(min(aliases))
        by_master[master] = states
    return {
        name + "." + state
        for name, master in common.items()
        for state in by_master.get(master, set())
    }


def configuration(
    top: str,
    sources: list[Path],
    libraries: list[Path],
    checks: list[dict[str, Any]],
    declared: list[set[str]],
    *,
    strategy: str = "sat",
    state_points: set[str] | None = None,
) -> str:
    if strategy not in {"sat", "abc-pdr"}:
        raise ValueError("Unknown EQY strategy: " + strategy)
    if state_points and strategy != "abc-pdr":
        raise ValueError("Model-derived state matching requires qualified PDR")
    lines = []
    for name, source, checked in zip(("gold", "gate"), sources, checks, strict=True):
        lines += [f"[{name}]"]
        lines += [
            f'read_liberty -ignore_miss_func -ignore_miss_dir "{p}"' for p in libraries
        ]
        lines += [f'read_verilog "{source}"']
        lines += ["delete t:" + kind for kind in checked["zero_port_types"]]
        lines += ["prep -top " + top + " -flatten", "delete t:$scopeinfo", ""]
    lines += ["[match *]", "nodefault"]
    # Keep every actual port and the netlist's declared hierarchical wires.
    # Routed flat names (netNNN, clknet_leaf_N_clk, etc.) are not semantic
    # correspondences across independently optimized layouts. A wildcard here
    # would cut their drivers and can produce spurious output counterexamples.
    # A dot also occurs in generated Liberty pin aliases after flattening;
    # those aliases must not form tens of thousands of redundant cut points.
    names = set(checks[0]["ports"]) | {
        name for name in declared[0] & declared[1] if "." in name
    }
    lines += ["final-gold-match /" + re.escape(name) + "/" for name in sorted(names)]
    if state_points:
        # One exact alternation avoids rescanning the entire flattened ID table
        # separately for thousands of individual register states.
        lines += [
            "final-gold-match /(?:"
            + "|".join(re.escape(name) for name in sorted(state_points))
            + ")/"
        ]
    lines += [
        r"gold-nomatch /.*\..*/",
        r"gate-nomatch /.*\..*/",
        r"gold-nomatch /n[0-9]+|_[0-9]+_/",
        r"gate-nomatch /n[0-9]+|_[0-9]+_/",
        "",
    ]
    if strategy == "sat":
        lines += ["[strategy simple]", "use sat", "depth 10"]
    else:
        lines += [
            "[strategy pdr]",
            "use sby",
            "engine abc pdr",
            "depth 10",
            "xprop on",
            "option aigsmt z3",
        ]
    return "\n".join(lines) + "\n"


def proof_receipt(work: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not (work / "PASS").is_file() or (work / "FAIL").exists():
        raise ValueError("EQY did not prove the complete design")
    partitions = (work / "partition.list").read_text().splitlines()
    names = [line.split()[1] for line in partitions if line.strip()]
    if not names:
        raise ValueError("EQY produced no proof partitions")
    for name in names:
        statuses = list((work / "strategies" / name).glob("*/status"))
        if not any(path.read_text().strip() == "PASS" for path in statuses):
            raise ValueError("EQY partition remains unproven: " + name)
    bits = sum(
        p["width"] for p in checks[0]["ports"].values() if p["direction"] == "output"
    )
    return {"engine": "eqy", "proven_points": bits, "proven_partitions": len(names)}


def verify(
    jobs: Jobs,
    reference: dict[str, Any],
    candidate: dict[str, Any],
    libraries: list[Path],
    checks: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    folder, deployment = jobs.experiment, jobs.deployment
    policy = deployment.value.get("validation", {})
    strategy = policy.get("equivalence_strategy", "sat")
    top = deployment.design(candidate["design_id"])["top"]
    sources = [Path(frame["files"]["v"]) for frame in (reference, candidate)]
    models = [read(folder / (side + ".json")) for side in ("gold", "gate")]
    declared = [set(model["modules"][top]["netnames"]) for model in models]
    states = (
        common_flop_states(models[0], models[1], top)
        if policy.get("equivalence_match_flops", False)
        else set()
    )
    script, wrapper, work = folder / "proof.eqy", folder / "yosys", folder / "eqy-work"
    script.write_text(
        configuration(
            top,
            sources,
            libraries,
            checks,
            declared,
            strategy=strategy,
            state_points=states,
        )
    )
    # Suppress only the native partitioner's very large dependency matrix log.
    # The Yosys script, model, partitioner and exit status stay unchanged.
    wrapper.write_text(
        "#!/usr/bin/python3\nimport os,sys\n"
        f"real={deployment.value['tools']['yosys']!r}\n"
        "args=sys.argv[1:]\n"
        "if args and args[-1].endswith('partition.ys'):\n"
        " script=args.pop()\n args += ['-p','tee -q script '+script]\n"
        "os.execv(real,[real,*args])\n"
    )
    wrapper.chmod(0o755)
    command = [
        deployment.value["tools"]["eqy"],
        "--yosys",
        str(wrapper),
        "-j",
        str(policy.get("equivalence_jobs", 2)),
        "-d",
        str(work),
        str(script),
    ]
    extra: list[Path] = []
    details: dict[str, Any] = {"matching_policy": "ports-and-common-declared-hierarchy"}
    if policy.get("equivalence_match_flops", False):
        from .config import write

        matched_states = folder / "proof-state-matches.json"
        write(matched_states, {"count": len(states), "points": sorted(states)})
        extra.append(matched_states)
        details.update(
            matching_policy="ports-common-declared-hierarchy-and-model-flop-state",
            proposed_state_points=len(states),
        )
    if strategy == "abc-pdr":
        manifest_path = policy.get("equivalence_solver_manifest")
        if not manifest_path:
            raise ValueError("PDR proof requires a pinned solver manifest")
        solver = read(manifest_path)
        if (
            solver["name"] != "z3"
            or solver["image_sha256"] != deployment.value["toolchain"]["image_sha256"]
        ):
            raise ValueError("Proof solver does not match the qualified tool image")
        for field in ("binary", "library"):
            if digest(Path(solver[field]["path"])) != solver[field]["sha256"]:
                raise ValueError("Proof solver changed: " + field)
        saved_solver = folder / "proof-solver.json"
        shutil.copyfile(manifest_path, saved_solver)
        command[1:1] = [
            "--abc",
            str(Path(deployment.value["tools"]["yosys"]).with_name("yosys-abc")),
        ]
        launcher = folder / "launch-proof.py"
        launcher.write_text(
            "import os\n"
            f"os.environ['PATH']={str(Path(solver['binary']['path']).parent)!r}+os.pathsep+os.environ['PATH']\n"
            f"command={command!r}\n"
            "os.execv(command[0],command)\n"
        )
        command = ["python3", str(launcher)]
        extra.extend([saved_solver, launcher])
        details.update(strategy=strategy, solver=solver)
    record = jobs.command(
        "logic-eqy",
        container(deployment, command),
        capture=[
            script,
            wrapper,
            folder / "model-evidence.json",
            *sources,
            work / "PASS",
            work / "partition.list",
            work / "matched.ids",
            work / "logfile.txt",
            *extra,
        ],
        seconds=deployment.value.get("validation", {}).get("equivalence_seconds", 3600),
        cpu=4,
        memory_gib=deployment.value.get("validation", {}).get(
            "equivalence_memory_gib", 32
        ),
        parent=candidate["run_id"],
        objective=Path(candidate["objective"]),
    )
    jobs.log(record, folder / "proof.log")
    return record, {**proof_receipt(work, checks), **details}

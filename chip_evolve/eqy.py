"""Existing EQY partitioned proof under the same fixed Liberty models and EF."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import read
from .jobs import Jobs
from .physical import container


def configuration(
    top: str,
    sources: list[Path],
    libraries: list[Path],
    checks: list[dict[str, Any]],
    declared: list[set[str]],
) -> str:
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
    # A dot also occurs in generated Liberty pin aliases after flattening;
    # those aliases must not form tens of thousands of redundant cut points.
    names = set(checks[0]["ports"]) | {
        name for name in declared[0] & declared[1] if "." in name
    }
    lines += ["final-gold-match /" + re.escape(name) + "/" for name in sorted(names)]
    lines += [
        r"gold-nomatch /.*\..*/",
        r"gate-nomatch /.*\..*/",
        r"gold-nomatch /n[0-9]+|_[0-9]+_/",
        r"gate-nomatch /n[0-9]+|_[0-9]+_/",
        "gold-match *",
        "",
        "[strategy simple]",
        "use sat",
        "depth 10",
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
    top = deployment.design(candidate["design_id"])["top"]
    sources = [Path(frame["files"]["v"]) for frame in (reference, candidate)]
    declared = [
        set(read(folder / (side + ".json"))["modules"][top]["netnames"])
        for side in ("gold", "gate")
    ]
    script, wrapper, work = folder / "proof.eqy", folder / "yosys", folder / "eqy-work"
    script.write_text(configuration(top, sources, libraries, checks, declared))
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
    record = jobs.command(
        "logic-eqy",
        container(
            deployment,
            [
                deployment.value["tools"]["eqy"],
                "--yosys",
                str(wrapper),
                "-j",
                "2",
                "-d",
                str(work),
                str(script),
            ],
        ),
        capture=[
            script,
            wrapper,
            folder / "model-evidence.json",
            *sources,
            work / "PASS",
            work / "partition.list",
            work / "matched.ids",
            work / "logfile.txt",
        ],
        seconds=3600,
        cpu=4,
        memory_gib=32,
        parent=candidate["run_id"],
        objective=Path(candidate["objective"]),
    )
    jobs.log(record, folder / "proof.log")
    return record, proof_receipt(work, checks)

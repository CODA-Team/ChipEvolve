"""Freeze a qualified physical recipe and professional tool identities."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from eda_toolkits.objectives import require_same_conditions

from .candidates import result_frame
from .clock import flow_sdc
from .comparisons import compare
from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import container

SCHEMA = "chip-evolve.environment.v1"


def reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": digest(path)}


def identity(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in value.items() if k != "environment_id"}, sort_keys=True
        ).encode()
    ).hexdigest()


def deployment_binding(deployment: Deployment, design_id: str) -> dict[str, Any]:
    keys = (
        "runtime",
        "tools",
        "professional",
        "flow_tool_profile",
        "openroad_launcher",
        "goal_python",
        "client_python",
    )
    return {
        "design": deployment.design(design_id),
        **{key: deployment.value[key] for key in keys if key in deployment.value},
    }


def professional_files(deployment: Deployment) -> dict[str, Any]:
    prefixes = {
        "flow": ("flow", "config", "run.sh"),
        "dpl": ("scripts", "baseline"),
        "goal": ("goalevolve", "config"),
        "eco": ("src", "OpenROAD_utils"),
    }
    result = {}
    for name, binding in deployment.value["professional"].items():
        source = Path(binding["source"])
        if subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=source, text=True
        ).strip():
            raise ValueError(
                "Commit approved professional edits before freezing: " + name
            )
        names = (
            subprocess.check_output(
                ["git", "ls-files", "-z", "--", *prefixes[name]], cwd=source
            )
            .decode()
            .split("\0")
        )
        files = [
            source / n
            for n in names
            if n and Path(n).suffix in {".py", ".sh", ".tcl", ".json"}
        ]
        result[name] = {
            "commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip(),
            "files": [reference(p) for p in files if p.is_file()],
        }
        if "profile_template" in binding:
            result[name]["profile"] = reference(Path(binding["profile_template"]))
            profile = read(binding["profile_template"])
            declared = profile["toolchain"]
            commit = declared.get(
                "openroad_commit", declared.get("openroad_base_commit")
            )
            if commit != deployment.value["toolchain"]["openroad_commit"]:
                raise ValueError("Professional uses a different OpenROAD base: " + name)
            if "core_binary" in profile:
                result[name]["core_binary"] = reference(Path(profile["core_binary"]))
        if name == "dpl":
            installation = Path(binding["candidate_source"]) / "install/OpenROAD/bin"
            result[name]["binary"] = reference(installation / "openroad")
            result[name]["build_receipt"] = reference(
                installation / "platform-build.json"
            )
            if read(installation / "platform-build.json")["binary_sha256"] != digest(
                installation / "openroad"
            ):
                raise ValueError("DPL installation differs from its build receipt")
        if name == "goal":
            seed = Path(read(binding["profile_template"])["source_seed"])
            if subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=seed, text=True
            ).strip():
                raise ValueError("Goal source seed has uncommitted changes")
            result[name]["source_seed"] = str(seed)
            result[name]["source_seed_commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=seed, text=True
            ).strip()
    return result


def freeze_environment(
    deployment: Deployment, source_path: Path, qualification: Path, experiment: Path
) -> Path:
    """Use completed matching controls; the actual binary probe runs beneath EF."""
    source = result_frame(source_path)
    design = deployment.design(source["design_id"])
    recipe = read(qualification / "recipe.json")
    report = read(qualification / "comparison.json")
    control = result_frame(qualification / "result.json")
    require_same_conditions(source, control)
    actual_deltas = compare(source, control)["deltas"]
    if (
        recipe["source_run_id"] != source["run_id"]
        or recipe["result_sha256"] != digest(source_path)
        or report["reference_run_id"] != source["run_id"]
        or report["candidate_run_id"] != control["run_id"]
        or len(report["deltas"]) != 7
        or report["deltas"] != actual_deltas
        or any(row["delta"] != 0 for row in report["deltas"].values())
        or recipe["baseline_parameters"]["SYNTH_USE_SYN"] != "0"
    ):
        raise ValueError(
            "Need an actual seven-metric matching full-knob source control"
        )
    if design["platform"] != "asap7":
        raise ValueError("Current Goal/ECO deployment is qualified for ASAP7 only")
    flow_sdc(Path(recipe["sdc"]).read_text(), design["clock_period_ns"])
    image = Path(deployment.value["runtime"]["image"])
    if digest(image) != deployment.value["toolchain"]["image_sha256"]:
        raise ValueError("Image differs from its pinned identity")
    probe = experiment / "probe-tools.py"
    output = experiment / "tool-probe.json"
    tcl = experiment / "capabilities.tcl"
    tcl.write_text("help detailed_placement\nexit\n")
    probe.write_text(
        "import hashlib,json,subprocess\nfrom pathlib import Path\n"
        + "tools="
        + repr(deployment.value["tools"])
        + "\nresult={}\n"
        + "for name,flag in [('openroad','-version'),('yosys','-V')]:\n"
        + " p=Path(tools[name]); result[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'version':subprocess.check_output([str(p),flag],text=True).strip()}\n"
        + "result['detailed_placement_help']=subprocess.check_output([tools['openroad'],'-exit',"
        + repr(str(tcl))
        + "],text=True)\n"
        + "Path("
        + repr(str(output))
        + ").write_text(json.dumps(result,indent=2)+'\\n')\n"
    )
    jobs = Jobs(deployment, source["design_id"], experiment)
    record = jobs.command(
        "probe",
        container(deployment, ["python3", str(probe)]),
        cpu=1,
        memory_gib=4,
        seconds=300,
        capture=[probe, tcl, output],
        parent=source["run_id"],
    )
    if "-use_diamond_legalizer" not in read(output)["detailed_placement_help"]:
        raise ValueError("OpenROAD lacks the explicit original Diamond control")
    value = {
        "schema_version": SCHEMA,
        "design_id": source["design_id"],
        "objective_id": source["objective_id"],
        "condition_id": source["condition_id"],
        "deployment_binding": deployment_binding(deployment, source["design_id"]),
        "toolchain": deployment.value["toolchain"],
        "image": reference(image),
        "source": reference(source_path),
        "source_run_id": source["run_id"],
        "qualification": [
            reference(qualification / name)
            for name in ("recipe.json", "comparison.json", "result.json")
        ],
        "source_inputs": [
            {"path": p, "sha256": sha} for p, sha in recipe["input_sha256"].items()
        ],
        "measurement_inputs": [
            reference(Path(design["sdc"])),
            *[reference(Path(row["path"])) for row in design["libraries"]],
        ],
        "professionals": professional_files(deployment),
        "probe_run_id": record["run"]["run_id"],
        "probe": reference(output),
        "configuration_inputs": [
            reference(Path(deployment.value[key]))
            for key in ("flow_tool_profile", "openroad_launcher")
        ],
        "flow_recipe": "source",
        "capability_bounds": {
            "platform": "asap7",
            "physical_clocks": 1,
            "native_synthesis": "yosys",
            "native_scoring": "original TT/CP0",
            "final_scoring": "original frozen FF conditions",
            "code_variants": "common base plus private research increments",
            "builtin_full_hierarchy": False,
        },
    }
    value["environment_id"] = identity(value)
    path = experiment / "environment.json"
    write(path, value)
    return path


def check_environment(
    deployment: Deployment,
    path: Path,
    design_id: str,
    capability: str,
    source: Path | None,
    flow_recipe: str,
) -> dict[str, Any]:
    value = read(path)
    if value["schema_version"] != SCHEMA or value["environment_id"] != identity(value):
        raise ValueError("Frozen environment changed")
    if (
        value["design_id"] != design_id
        or value["toolchain"] != deployment.value["toolchain"]
    ):
        raise ValueError("Environment belongs to another design/toolchain")
    if value["deployment_binding"] != deployment_binding(deployment, design_id):
        raise ValueError(
            "Deployment tools, professional bindings or design inputs changed"
        )
    files = [
        value["image"],
        value["source"],
        value["probe"],
        *value["qualification"],
        *value["source_inputs"],
        *value["measurement_inputs"],
        *value["configuration_inputs"],
    ]
    for name, binding in value["professionals"].items():
        repositories = [
            (Path(deployment.value["professional"][name]["source"]), binding["commit"])
        ]
        if "source_seed" in binding:
            repositories.append(
                (Path(binding["source_seed"]), binding["source_seed_commit"])
            )
        for repository, commit in repositories:
            actual = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repository, text=True
            ).strip()
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repository, text=True
            ).strip()
            if actual != commit or dirty:
                raise ValueError(
                    "Frozen professional repository changed: " + str(repository)
                )
        files += binding["files"]
        files += [
            binding[key]
            for key in ("profile", "binary", "build_receipt", "core_binary")
            if key in binding
        ]
    for row in files:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Frozen environment file changed: " + row["path"])
    if capability == "flow" and flow_recipe != "source":
        raise ValueError("Qualified full Flow requires source mode, not legacy")
    if source:
        frame = result_frame(source)
        if (
            frame["design_id"] != design_id
            or frame["condition_id"] != value["condition_id"]
            or frame["objective_id"] != value["objective_id"]
        ):
            raise ValueError("Source differs from the qualified design/conditions")
        if capability == "flow" and frame["run_id"] != value["source_run_id"]:
            raise ValueError("Flow must start from its explicitly qualified source")
    return value

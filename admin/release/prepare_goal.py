"""Prepare GoalEvolve's GCD source and deployment from the pinned public inputs."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from native_toolchain import checkout, openroad_build_args
from stack import configuration, write
from profile_bridge import invoke


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_source(module, destination, metadata):
    checkout(
        destination,
        "https://github.com/The-OpenROAD-Project/OpenROAD.git",
        metadata["openroad_commit"],
    )
    git = ["git", "-C", str(destination)]
    for name, expected in metadata["patch_sha256"].items():
        patch = module / "toolchain/common" / name
        if digest(patch) != expected:
            raise ValueError(
                f"GoalEvolve patch differs from its declared SHA-256: {name}"
            )
    for name in ("rsz.patch", "rmp.patch", "build_api.patch"):
        subprocess.run(
            [*git, "apply", "--index", module / "toolchain/common" / name], check=True
        )
    for name, expected in metadata["professional_files"].items():
        if digest(destination / name) != expected:
            raise ValueError(f"Patched OpenROAD source differs: {name}")
    subprocess.run(
        [
            *git,
            "-c",
            "user.name=ChipEvolve",
            "-c",
            "user.email=local@chipevolve.invalid",
            "commit",
            "--quiet",
            "-m",
            "Apply GoalEvolve's qualified OpenROAD patches",
        ],
        check=True,
    )


def prepare_pdk(deployment, directory, *, layout):
    library = Path(deployment["designs"]["gcd"]["libraries"][0]["path"])
    (directory / "lib").mkdir(parents=True)
    runtime = deployment["runtime"]
    command = [
        runtime["executable"],
        "exec",
        "--cleanenv",
        "--no-home",
        runtime["image"],
        "cat",
    ]
    for name in (
        "setRC.tcl",
        "rcx_patterns.rules",
        "LICENSE",
        "README.md",
        "lef/NangateOpenCellLibrary.tech.lef",
        "lef/NangateOpenCellLibrary.macro.mod.lef",
    ):
        target = directory / name
        target.parent.mkdir(exist_ok=True)
        with target.open("wb") as stream:
            subprocess.run(
                [*command, layout["platforms_root"] + "/nangate45/" + name],
                stdout=stream,
                check=True,
            )
    cells = sorted(
        set(
            re.findall(r"(?m)^\s*cell\s*\(\s*([A-Za-z0-9_]+)\s*\)", library.read_text())
        )
    )
    if not cells:
        raise ValueError("The Nangate45 Liberty does not declare any cell masters")
    (directory / "equivalent_cells.csv").write_text("\n".join(cells) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, required=True, help="stack configuration from init"
    )
    parser.add_argument("--build-memory-gib", type=int)
    args = parser.parse_args()
    stack = configuration(args.config)
    root = Path(stack["workspace"])
    layout = invoke(root, "layout")
    state = Path(stack["state_root"])
    build_budget = invoke(
        root,
        "admit-build",
        deployment=str(state / "local.json"),
        memory_gib=args.build_memory_gib,
    )
    args.build_memory_gib = build_budget["memory_bytes"] >> 30
    build_defaults = invoke(root, "preset", kind="code-build")
    analysis_defaults = invoke(root, "preset", kind="code-analysis")
    physical_defaults = invoke(root, "preset", kind="gcd-code-physical")
    deployment = json.loads((state / "local.json").read_text())
    module = root / "agent/goalevolve"
    python = module / ".venv/bin/python"
    if not python.is_file():
        parser.error("Install GoalEvolve's environment using bootstrap.py")
    metadata = json.loads((module / "toolchain/common_toolchain.json").read_text())
    output = state / "goal-preparation"
    output.mkdir(exist_ok=False)
    seed = output / "openroad"
    prepare_source(module, seed, metadata)
    pdk = output / "nangate45"
    prepare_pdk(deployment, pdk, layout=layout)
    cpu = build_budget["cpu_cores"]
    profile = {
        "source_seed": str(seed),
        "image": deployment["runtime"]["image"],
        "toolchain": {
            **deployment["toolchain"],
            **{
                key: metadata[key]
                for key in ("orfs_commit", "openroad_commit", "opensta_commit")
            },
        },
        "codex": {
            "auth_mode": "existing_codex",
            "home": str(
                Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
            ),
            "config_path": str(module / "config/codex.json"),
        },
        "resources": {
            "build": {
                "cpu_cores": cpu,
                "memory_bytes": args.build_memory_gib << 30,
                "processes": build_defaults["processes"],
            },
            "analysis": {
                "cpu_cores": analysis_defaults["cpu_cores"],
                "memory_bytes": analysis_defaults["memory_gib"] << 30,
                "processes": analysis_defaults["processes"],
            },
        },
        "container_environment": {
            "OMP_NUM_THREADS": str(cpu),
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
        "cmake_args": openroad_build_args(seed, workspace=root),
    }
    profile_path, campaign_path = output / "profile.json", output / "campaign.json"
    write(profile_path, profile)
    campaign = json.loads((module / "experiments/ae3_base.json").read_text())
    campaign.update(
        build_jobs=cpu,
        planning_mode="ast_graph",
        repository_graph_enabled=True,
        target_metrics={"tns_abs_ns": 0, "dynamic_power_pw": 0, "leakage_power_pw": 0},
    )
    write(campaign_path, campaign)
    deployment["goal_python"] = str(python)
    deployment.setdefault("professional", {})["goal"] = {
        "source": str(module),
        "profile_template": str(profile_path),
        "campaign_template": str(campaign_path),
        "pdk_template": str(pdk),
        "official_checker": str(module / "third_party/official_checker"),
        "physical_memory_gib": physical_defaults["memory_gib"],
    }
    deployment["designs"]["gcd"].update(
        signal_layers="metal2-metal10", clock_layers="metal4-metal10"
    )
    write(state / "local.json", deployment)
    print(profile_path)


if __name__ == "__main__":
    main()

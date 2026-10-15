"""Prepare the actual registered ORFS recipe without changing native search."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import container, measure, publish


def source_binding(source_result: Path) -> dict[str, Any]:
    """Use recorded submitted bytes, not the deployment's current defaults."""
    frame = read(source_result)
    folder = source_result.parent / "jobs/orfs"
    task = read(folder / "task.json")
    submitted = read(folder / "submission.json")
    if (
        frame["physical_run_id"] != submitted["run"]["run_id"]
        or frame["design_id"] != task["design_id"]
        or task["inputs"]["adapter"] != "orfs_flow"
    ):
        raise ValueError("Source does not own the recorded ORFS recipe")
    frozen_inputs = folder / "staged-hashes.json"
    if not frozen_inputs.is_file():
        raise ValueError(
            "Source lacks frozen input hashes; select a complete registered recipe "
            "or reconstruct an explicitly labelled qualification baseline"
        )
    hashes = read(frozen_inputs)
    dependencies = source_result.parent / "recipe-dependencies.json"
    dependency_hashes = read(dependencies) if dependencies.is_file() else {}
    hashes = {**hashes, **dependency_hashes}
    for name, sha in hashes.items():
        if digest(Path(name)) != sha:
            raise ValueError("Registered source input changed: " + name)
    staged = {item["destination"]: item["source"] for item in task["staged_inputs"]}
    inputs = task["inputs"]
    primary = {inputs["config_path"], inputs["sdc_path"], *inputs["liberty_paths"]}
    return {
        "design_id": frame["design_id"],
        "source_run_id": frame["run_id"],
        "physical_run_id": frame["physical_run_id"],
        "result_sha256": digest(source_result),
        "image": inputs["orfs_image"],
        "design_config": inputs["design_config"],
        "config": staged[inputs["config_path"]],
        "sdc": staged[inputs["sdc_path"]],
        "libraries": [staged[name] for name in inputs["liberty_paths"]],
        "input_sha256": hashes,
        "recipe_dependencies": dependency_hashes,
        "auxiliary_inputs": {
            "/work/" + k: v for k, v in staged.items() if k not in primary
        },
    }


def snapshot_script(destination: Path, platform: str) -> str:
    """This script runs in the pinned image beneath an EF command task."""
    return (
        "import hashlib,json,shutil\nfrom pathlib import Path\n"
        "origin=Path('/OpenROAD-flow-scripts/flow')\n"
        f"target=Path({str(destination)!r})\n"
        f"platform={platform!r}\n"
        "target.mkdir(parents=True)\n"
        "excluded={'.git','results','logs','reports','objects','__pycache__'}\n"
        "for p in origin.iterdir():\n"
        " if p.name in excluded: continue\n"
        " if p.name=='platforms':\n"
        "  (target/p.name).mkdir()\n"
        "  shutil.copytree(p/platform,target/p.name/platform)\n"
        "  shutil.copytree(p/'common',target/p.name/'common')\n"
        " elif p.is_dir():\n"
        "  shutil.copytree(p,target/p.name,ignore=shutil.ignore_patterns(*excluded))\n"
        " else: shutil.copy2(p,target/p.name)\n"
        "files={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() "
        "for p in sorted(target.rglob('*')) if p.is_file()}\n"
        "(target.parent/'image-files.json').write_text(json.dumps(files,indent=2)+'\\n')\n"
    )


def bind_config(flow: Path, binding: dict[str, Any]) -> Path:
    """Relocate includes, preserving all submitted configuration overrides."""
    source_config = Path(binding["config"]).read_text()
    original = "/OpenROAD-flow-scripts/flow/" + binding["design_config"]
    if original not in source_config:
        raise ValueError("Source wrapper does not include its recorded design config")
    source_config = source_config.replace(
        original, str(flow / binding["design_config"])
    )
    bound = flow / "source-bindings"
    bound.mkdir()
    for index, (name, original_path) in enumerate(
        binding.get("auxiliary_inputs", {}).items()
    ):
        target = bound / ("input-" + str(index) + "-" + Path(name).name)
        shutil.copyfile(original_path, target)
        source_config = source_config.replace(name, str(target))
    for index, name in enumerate(binding.get("recipe_dependencies", {})):
        target = bound / ("dependency-" + str(index) + "-" + Path(name).name)
        shutil.copyfile(name, target)
        source_config = source_config.replace(name, str(target))
    sdc = bound / "design.sdc"
    shutil.copyfile(binding["sdc"], sdc)
    libraries = []
    for index, name in enumerate(binding["libraries"]):
        target = bound / (str(index) + "-" + Path(name).name)
        shutil.copyfile(name, target)
        libraries.append(str(target))
    config = flow / "source-config.mk"
    config.write_text(
        source_config
        + "\n# Actual submitted source bindings; protect them from platform defaults.\n"
        + "override export LIB_FILES = "
        + " ".join(libraries)
        + "\nexport SDC_FILE = "
        + str(sdc)
        + "\n"
    )
    return config


def prepare_flow_recipe(
    deployment: Deployment, source_result: Path, experiment: Path
) -> Path:
    binding = source_binding(source_result)
    frame = read(source_result)
    if frame["conditions"]["toolchain"] != deployment.value["toolchain"]:
        raise ValueError("Source recipe uses a different toolchain")
    image = Path(binding["image"])
    if image.resolve() != Path(deployment.value["runtime"]["image"]).resolve():
        raise ValueError("Source recipe uses a different image")
    if digest(image) != deployment.value["toolchain"]["image_sha256"]:
        raise ValueError("Source image differs from its frozen identity")
    source = experiment / "source"
    flow = source / "flow"
    script = experiment / "snapshot-flow.py"
    script.write_text(
        snapshot_script(flow, deployment.design(binding["design_id"])["platform"])
    )
    jobs = Jobs(deployment, binding["design_id"], experiment)
    record = jobs.command(
        "prepare-recipe",
        container(deployment, ["/usr/bin/python3", str(script)]),
        capture=[script, source / "image-files.json"],
        parent=binding["physical_run_id"],
        seconds=1800,
        cpu=2,
        memory_gib=8,
    )
    config = bind_config(flow, binding)
    formal = Path(deployment.value["professional"]["flow"]["source"])
    for name in ("eval_tns.tcl", "eval_tns.sh"):
        shutil.copyfile(formal / "flow" / name, flow / name)
    image_files = read(source / "image-files.json")
    tree = hashlib.sha256(json.dumps(image_files, sort_keys=True).encode()).hexdigest()
    write(
        experiment / "recipe.json",
        {
            "schema_version": "chip-evolve.flow-source-recipe.v1",
            **binding,
            "source_result": str(source_result.resolve()),
            "source": str(source),
            "config_path": str(config),
            "physical_tree_sha256": tree,
            "image_sha256": deployment.value["toolchain"]["image_sha256"],
            "toolchain": deployment.value["toolchain"],
            "resolved_config_sha256": digest(config),
            "preparation_run_id": record["run"]["run_id"],
            "native_search_qualified": False,
            "qualification_note": "Physical source prepared; native knob qualification is separate",
        },
    )
    return source


NATIVE_PARAMETERS = (
    "SYNTH_USE_SYN",
    "SYNTH_HIERARCHICAL",
    "CORE_UTILIZATION",
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
    "ENABLE_DPO",
    "PLACE_DENSITY_LB_ADDON",
    "TNS_END_PERCENT",
    "CTS_CLUSTER_SIZE",
    "CTS_CLUSTER_DIAMETER",
    "FLOORPLAN_PIN_LAYER_ADJUST",
    "FLOORPLAN_ABOVE_LAYER_ADJUST",
    "PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST",
    "FASTROUTE_TCL",
    "PRE_GLOBAL_ROUTE_TCL",
)


def resolve_native_parameters(
    deployment: Deployment, experiment: Path, recipe: dict[str, Any]
) -> dict[str, str]:
    """Inspect the real Make expansion through EF; unset is not numeric zero."""
    flow = Path(recipe["source"]) / "flow"
    inspector = experiment / "inspect-native.mk"
    output = experiment / "resolved-native-parameters.json"
    code = "import json,sys;from pathlib import Path;Path(sys.argv[1]).write_text(json.dumps(dict(zip(sys.argv[2::2],sys.argv[3::2])),indent=2))"
    values = " ".join(
        name + ' "$(if $(strip $(' + name + ")),$(" + name + '),__UNSET__)"'
        for name in NATIVE_PARAMETERS
    )
    inspector.write_text(
        ".PHONY: chip-evolve-inspect\nchip-evolve-inspect:\n"
        + "\t@/usr/bin/python3 -c '"
        + code
        + "' "
        + str(output)
        + " "
        + values
        + "\n"
    )
    jobs = Jobs(deployment, recipe["design_id"], experiment)
    jobs.command(
        "inspect-native-parameters",
        container(
            deployment,
            [
                "/usr/bin/make",
                "-s",
                "-C",
                str(flow),
                "-f",
                "Makefile",
                "-f",
                str(inspector),
                "FLOW_HOME=" + str(flow),
                "WORK_HOME=" + str(flow),
                "DESIGN_CONFIG=" + recipe["config_path"],
                "chip-evolve-inspect",
            ],
        ),
        capture=[inspector, output],
        parent=recipe["physical_run_id"],
        seconds=300,
        cpu=1,
        memory_gib=4,
    )
    values = read(output)
    if values["SYNTH_USE_SYN"] != "0":
        raise ValueError(
            "Full native hierarchy requires a registered Yosys source (SYNTH_USE_SYN=0); builtin synthesis remains unqualified"
        )
    missing = [key for key, value in values.items() if value == "__UNSET__"]
    if missing:
        raise ValueError(
            "Register an explicit full-knob source before search; unset values: "
            + ", ".join(missing)
        )
    values["SYNTH_FLATTEN"] = str(1 - int(values["SYNTH_HIERARCHICAL"]))
    write(experiment / "baseline-parameters.json", values)
    return values


def prepare_native_source(
    deployment: Deployment, source_result: Path, experiment: Path
) -> Path:
    """Overlay only native control code, preserving the pinned physical flow."""
    from .professional import freeze, inventory

    source = prepare_flow_recipe(deployment, source_result, experiment)
    recipe_path = experiment / "recipe.json"
    recipe = read(recipe_path)
    resolve_native_parameters(deployment, experiment, recipe)
    formal = Path(deployment.value["professional"]["flow"]["source"])
    controller = experiment / "native-controller"
    paths = ["run.sh", "config", "flow/predict_model"]
    paths += [
        str(p.relative_to(formal))
        for p in (formal / "flow").iterdir()
        if p.is_file() and p.suffix in {".py", ".sh", ".json"}
    ]
    freeze(formal, controller, paths=paths)
    shutil.copytree(controller / "config", source / "config")
    shutil.copyfile(controller / "run.sh", source / "run.sh")
    for path in (controller / "flow").iterdir():
        target = source / "flow" / path.name
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copyfile(path, target)
    # Keep the image's original design config as an include, before installing
    # the native base-config entry point at its customary path.
    base = source / "flow" / recipe["design_config"]
    original = base.with_name("source-original.mk")
    shutil.copyfile(base, original)
    config = Path(recipe["config_path"])
    config.write_text(config.read_text().replace(str(base), str(original)))
    base.write_text("include " + str(config) + "\n")
    recipe.update(
        resolved_config_sha256=digest(config),
        native_controller_sha256=inventory(controller),
        baseline_parameters=read(experiment / "baseline-parameters.json"),
        native_search_qualified=False,
        qualification_note="Full-knob Yosys source prepared; actual campaign consumption remains to be verified",
    )
    write(source / "prepared-files.json", inventory(source))
    write(recipe_path, recipe)
    return source


def qualify_prepared_recipe(
    deployment: Deployment, experiment: Path, *, seconds: int = 3600
) -> dict[str, Any]:
    """Run the unchanged physical recipe; this does not qualify native knobs."""
    import zipfile

    from .professional import tool_profile

    recipe = read(experiment / "recipe.json")
    reference = read(recipe["source_result"])
    source = Path(recipe["source"])
    config = Path(recipe["config_path"])
    if digest(config) != recipe["resolved_config_sha256"]:
        raise ValueError("Prepared source configuration changed")
    jobs = Jobs(deployment, recipe["design_id"], experiment)
    profile = tool_profile(deployment, source, experiment)
    parent = recipe["physical_run_id"]
    checkpoint: Path | None = None
    objective = Path(reference["objective"])
    record: dict[str, Any] = {}
    for stage in ("place", "cts", "route_finish"):
        inputs = {
            "adapter": "a2_stage",
            "stage": stage,
            "threads": 8,
            "profile_path": "inputs/profile.json",
            "config_path": "inputs/config.mk",
            "sdc_path": "inputs/design.sdc",
        }
        staged = [
            {"source": str(p), "destination": "inputs/" + name}
            for p, name in (
                (profile, "profile.json"),
                (config, "config.mk"),
                (source / "flow/source-bindings/design.sdc", "design.sdc"),
            )
        ]
        if checkpoint:
            inputs["checkpoint_path"] = "inputs/checkpoint.zip"
            staged.append(
                {"source": str(checkpoint), "destination": "inputs/checkpoint.zip"}
            )
        record = jobs.submit(
            stage, inputs, staged, parent=parent, objective=objective, seconds=seconds
        )
        checkpoint = experiment / (stage + ".zip")
        jobs.materialize(record, "flow_archive", checkpoint)
        parent = record["run"]["run_id"]
    files = {}
    for suffix, kind in (("odb", "raw_design_database"), ("spef", "raw_parasitics")):
        path = experiment / ("6_final." + suffix)
        jobs.materialize(record, kind, path, suffix="/6_final." + suffix)
        files[suffix] = path
    measured = measure(
        jobs,
        "common",
        files["odb"],
        files["spef"],
        Path(recipe["sdc"]),
        parent,
        objective,
    )
    assert checkpoint is not None
    with zipfile.ZipFile(checkpoint) as archive:
        route = json.loads(archive.read("flow/logs/5_2_route.json"))
    measured.update(
        route_drc=route["detailedroute__route__drc_errors"],
        flow_archive=str(checkpoint),
        flow_recipe=str(experiment / "recipe.json"),
        native_config=str(config),
        native_flow_dir=str(source / "flow"),
        native_method={
            "kind": "unchanged-source-physical-qualification",
            "source_run_id": recipe["source_run_id"],
            "native_search_executed": False,
        },
    )
    result = publish(jobs, measured)
    write(experiment / "result.json", result)
    return result


def inherit_prepared_source(frame: dict[str, Any], experiment: Path) -> Path:
    """Continue the source physical scripts instead of the global legacy tree."""
    recipe = read(frame["flow_recipe"])
    source = Path(recipe["source"])
    identity = source / "prepared-files.json"
    identity_root = source if identity.exists() else source / "flow"
    for name, sha in read(
        identity if identity.exists() else source / "image-files.json"
    ).items():
        if digest(identity_root / name) != sha:
            raise ValueError("Prepared physical source changed: " + name)
    if digest(Path(recipe["config_path"])) != recipe["resolved_config_sha256"]:
        raise ValueError("Prepared source configuration changed")
    target = experiment / "source"
    shutil.copytree(source, target)
    write(
        experiment / "inherited-recipe.json",
        {
            "source_recipe": frame["flow_recipe"],
            "source_recipe_sha256": digest(Path(frame["flow_recipe"])),
            "physical_tree_sha256": recipe["physical_tree_sha256"],
            "source": str(target),
        },
    )
    return target

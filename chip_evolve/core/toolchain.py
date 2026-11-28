"""Identity-bound root integration profile for the installed Toolkits layout."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from chip_evolve.core.config import Deployment, read, write
from chip_evolve.core.contracts import BusinessInputError, FileRef

PROFILE_DIRECTORY = Path(__file__).with_name("profiles")


def profile_object(value: object, field: str) -> dict[str, object]:
    """Check JSON object keys without trusting an unparameterized wire mapping."""
    if not isinstance(value, Mapping):
        raise BusinessInputError("invalid_profile", field, "object required")
    result: dict[str, object] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str):
            raise BusinessInputError("invalid_profile", field, "string keys required")
        result[key] = item
    return result


def profile_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BusinessInputError("invalid_profile", field, "nonempty text required")
    return value


def profile_records(value: object, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise BusinessInputError("invalid_profile", field, "array of objects required")
    return [profile_object(item, field) for item in cast(Sequence[object], value)]


def profile_document(path: Path) -> dict[str, object]:
    return profile_object(json.loads(path.read_text()), str(path))


def file_ref(path: Path) -> FileRef:
    with path.open("rb") as stream:
        return FileRef(
            path.resolve(), hashlib.file_digest(stream, "sha256").hexdigest()
        )


def check_ref(reference: FileRef) -> None:
    if file_ref(reference.path) != reference:
        raise BusinessInputError(
            "profile_identity_changed", str(reference.path), "SHA256 differs"
        )


def layout_paths() -> dict[str, str]:
    """The only default container layout, shared by runtime and release callers."""
    value = profile_document(PROFILE_DIRECTORY / "orfs-common-v1.json")
    if value.get("schema_version") != "chip-evolve.layout.v1":
        raise BusinessInputError("unsupported_layout_schema", "layout", "expected v1")
    paths = profile_object(value.get("layout"), "layout")
    required = {
        "orfs_root",
        "flow_root",
        "makefile",
        "platforms_root",
        "openroad",
        "yosys",
        "python",
        "make",
        "boost_cmake",
        "ortools",
    }
    if set(paths) != required or not all(
        isinstance(path, str) and path.startswith("/") for path in paths.values()
    ):
        raise BusinessInputError(
            "invalid_layout", "layout", "absolute tool paths required"
        )
    return {key: profile_text(value, "layout." + key) for key, value in paths.items()}


@dataclass(frozen=True)
class ImageLayoutProfile:
    origin: FileRef
    profile_id: str
    image: FileRef
    architecture: str
    template: FileRef
    policy: FileRef
    layout: Mapping[str, str]


RuntimeProfileRef = ImageLayoutProfile


def ref_payload(reference: FileRef) -> dict[str, str]:
    return {"path": str(reference.path), "sha256": reference.sha256}


def parse_ref(value: object, field: str) -> FileRef:
    value = profile_object(value, field)
    if not isinstance(value.get("path"), str):
        raise BusinessInputError(
            "invalid_profile_reference", field, "path/SHA object required"
        )
    digest = value.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise BusinessInputError("invalid_profile_reference", field, "SHA256 required")
    result = FileRef(Path(profile_text(value["path"], field + ".path")), digest)
    if not result.path.is_absolute():
        raise BusinessInputError(
            "invalid_profile_reference", field, "absolute path required"
        )
    check_ref(result)
    return result


def profile_id(value: Mapping[str, object]) -> str:
    payload = {key: item for key, item in value.items() if key != "profile_id"}
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def load_runtime_profile(deployment: Deployment) -> ImageLayoutProfile:
    reference = parse_ref(deployment.value.get("runtime_profile"), "runtime_profile")
    value = profile_document(reference.path)
    required = {
        "schema_version",
        "profile_id",
        "image",
        "architecture",
        "template",
        "policy",
        "layout",
        "binaries",
        "source_family",
        "toolkit",
        "plugins",
    }
    if set(value) != required:
        raise BusinessInputError(
            "invalid_profile",
            str(reference.path),
            "exact runtime profile fields required",
        )
    toolkit = profile_object(value["toolkit"], "toolkit")
    if (
        toolkit.get("distribution") != "eda-toolkits"
        or not isinstance(toolkit.get("version"), str)
        or not isinstance(toolkit.get("files"), list)
        or not toolkit["files"]
    ):
        raise BusinessInputError(
            "invalid_profile",
            "toolkit",
            "installed distribution and nonempty RECORD evidence required",
        )
    if value.get("schema_version") != "chip-evolve.runtime-profile.v1":
        raise BusinessInputError(
            "unsupported_profile_schema", str(reference.path), "expected v1"
        )
    if value.get("profile_id") != profile_id(value):
        raise BusinessInputError(
            "profile_identity_changed", str(reference.path), "content identity differs"
        )
    template = parse_ref(value.get("template"), "template")
    if (
        template != file_ref(PROFILE_DIRECTORY / "orfs-common-v1.json")
        or value.get("layout") != layout_paths()
    ):
        raise BusinessInputError(
            "unsupported_toolkit_layout",
            "layout",
            "fixed Toolkits layout family required",
        )
    policy = parse_ref(value.get("policy"), "policy")
    if policy != file_ref(PROFILE_DIRECTORY / "resources-v1.json"):
        raise BusinessInputError(
            "resource_policy_changed", "policy", "versioned policy differs"
        )
    image = parse_ref(value.get("image"), "image")
    architecture = value.get("architecture")
    if architecture != platform.machine():
        raise BusinessInputError(
            "profile_architecture_changed", "architecture", "host differs"
        )
    for row in profile_records(toolkit["files"], "toolkit.files"):
        if not isinstance(row.get("relative_path"), str):
            raise BusinessInputError(
                "invalid_profile", "toolkit.files", "installed relative path required"
            )
        parse_ref(row, "toolkit.files")
    actual = toolkit_identity(Path(sys.executable))

    def code_identity(identity: dict[str, object]) -> tuple[str, list[tuple[str, str]]]:
        return profile_text(identity["version"], "toolkit.version"), sorted(
            (
                profile_text(item["relative_path"], "relative_path"),
                profile_text(item["sha256"], "sha256"),
            )
            for item in profile_records(identity["files"], "toolkit.files")
        )

    if code_identity(actual) != code_identity(toolkit):
        raise BusinessInputError(
            "toolkit_consumer_changed", "toolkit", "current installed consumer differs"
        )
    family = profile_object(value["source_family"], "source_family")
    if family.get("layout_family") != "toolkits-orfs-common-v1":
        raise BusinessInputError(
            "invalid_profile", "source_family", "fixed consumer family required"
        )
    parse_ref(family.get("module_manifest"), "source_family.module_manifest")
    plugins = profile_records(value["plugins"], "plugins")
    if len(plugins) != 2:
        raise BusinessInputError(
            "invalid_profile", "plugins", "configured manifest and provenance required"
        )
    for row in plugins:
        parse_ref(row, "plugins")
    manifest = profile_document(Path(profile_text(plugins[0]["path"], "plugins.path")))
    if profile_object(manifest.get("environment"), "plugins.environment").get(
        "EDA_ORFS_IMAGE"
    ) != str(image.path):
        raise BusinessInputError(
            "profile_projection_changed", "plugins", "configured plugin image differs"
        )
    binaries = profile_object(value["binaries"], "binaries")
    if set(binaries) != {
        "openroad",
        "yosys",
        "python",
        "make",
    }:
        raise BusinessInputError(
            "invalid_profile", "binaries", "four measured tools required"
        )
    for name, raw_binary in binaries.items():
        binary = profile_object(raw_binary, "binaries." + name)
        if (
            binary.get("path") != layout_paths()[name]
            or not isinstance(binary.get("sha256"), str)
            or len(profile_text(binary["sha256"], "binaries.sha256")) != 64
        ):
            raise BusinessInputError(
                "invalid_profile", "binaries." + name, "measured tool identity required"
            )
    if deployment.value["runtime"]["image"] != str(image.path):
        raise BusinessInputError(
            "profile_projection_changed", "runtime.image", "image differs"
        )
    for name in ("openroad", "yosys"):
        if deployment.value["tools"][name] != layout_paths()[name]:
            raise BusinessInputError(
                "profile_projection_changed", "tools." + name, "tool differs"
            )
    return ImageLayoutProfile(
        reference,
        profile_text(value["profile_id"], "profile_id"),
        image,
        profile_text(architecture, "architecture"),
        template,
        policy,
        layout_paths(),
    )


def require_layout(deployment: Deployment) -> Mapping[str, str]:
    """Historical direct helpers retain the fixed layout; new dispatch validates profiles."""
    if "runtime_profile" in deployment.value:
        return load_runtime_profile(deployment).layout
    return layout_paths()


def installed_identity(python: Path, distribution: str) -> dict[str, object]:
    """Read the installed distribution, never a sibling checkout's internal API."""
    program = """import base64,hashlib,importlib.metadata as m,json,sys
d=m.distribution(sys.argv[1]); prefix=sys.argv[1].replace('-','_')+'/'; files=[]
for item in d.files or []:
 if item.hash is None or not str(item).startswith(prefix):
  continue
 p=d.locate_file(item).resolve(); data=p.read_bytes(); digest=hashlib.sha256(data).digest()
 if item.hash.mode!='sha256' or base64.urlsafe_b64encode(digest).rstrip(b'=').decode()!=item.hash.value:
  raise ValueError('Installed Toolkits RECORD mismatch: '+str(item))
 files.append({'path':str(p),'sha256':digest.hex(),'relative_path':str(item)})
if not files: raise ValueError('Installed Toolkits code files missing')
print(json.dumps({'distribution':sys.argv[1],'version':d.version,'files':files}))
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"}
    }
    return profile_object(
        json.loads(
            subprocess.check_output(
                [str(python), "-I", "-c", program, distribution],
                cwd="/tmp",
                env=env,
                text=True,
            )
        ),
        "installed_toolkit",
    )


def toolkit_identity(python: Path) -> dict[str, object]:
    return installed_identity(python, "eda-toolkits")


def bind_runtime_profile(workspace: Path, stack_config: dict[str, Any]) -> FileRef:
    """Materialize once from actual image bytes, tools and installed consumer identity."""
    state = Path(stack_config["state_root"])
    destination = state / "runtime-profile.json"
    runtime = stack_config.get("container_runtime", "apptainer")
    paths = layout_paths()
    image = file_ref(Path(stack_config["orfs_image"]))
    command = [runtime, "exec", "--cleanenv", "--no-home", str(image.path)]
    binaries = {}
    for name in ["openroad", "yosys", "python", "make"]:
        output = (
            subprocess.check_output([*command, "sha256sum", paths[name]], text=True)
            .strip()
            .split()
        )
        if len(output) != 2 or output[1] != paths[name]:
            raise BusinessInputError(
                "invalid_tool_probe", name, "unexpected binary path"
            )
        binaries[name] = {"path": output[1], "sha256": output[0]}
    for name in ["flow_root", "platforms_root"]:
        subprocess.run([*command, "test", "-d", paths[name]], check=True)
    subprocess.run([*command, "test", "-f", paths["makefile"]], check=True)
    toolkit_python = workspace / "toolkits/.venv/bin/python"
    plugins_root = state / "plugins"
    plugin = plugins_root / "openroad-data/openroad-data.plugin.json"
    provenance = plugin.with_name("provenance.json")
    if not plugin.exists():
        configure = [
            str(toolkit_python),
            "-I",
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(plugins_root),
            "--image",
            str(image.path),
        ]
        if "activity_lock" in stack_config:
            configure += ["--activity-lock", stack_config["activity_lock"]]
        subprocess.run(
            configure, check=True, capture_output=True, text=True, cwd="/tmp"
        )
    configured = read(plugin)
    if configured.get("environment", {}).get("EDA_ORFS_IMAGE") != str(
        image.path
    ) or configured.get("adapter_entry", [None])[0] != str(toolkit_python):
        raise BusinessInputError(
            "profile_projection_changed",
            "plugins",
            "configured consumer or image differs",
        )
    value = {
        "schema_version": "chip-evolve.runtime-profile.v1",
        "image": ref_payload(image),
        "architecture": subprocess.check_output(
            [*command, "uname", "-m"], text=True
        ).strip(),
        "template": ref_payload(file_ref(PROFILE_DIRECTORY / "orfs-common-v1.json")),
        "policy": ref_payload(file_ref(PROFILE_DIRECTORY / "resources-v1.json")),
        "layout": paths,
        "binaries": binaries,
        "source_family": {
            "layout_family": "toolkits-orfs-common-v1",
            "module_manifest": ref_payload(
                file_ref(workspace / "SOURCE_MANIFEST.json")
            ),
            "qualification": "Fixed SIF bytes and binary identities; source provenance is retained separately in the qualified image producer evidence.",
        },
        "toolkit": toolkit_identity(workspace / "toolkits/.venv/bin/python"),
        "plugins": [ref_payload(file_ref(plugin)), ref_payload(file_ref(provenance))],
    }
    value["profile_id"] = profile_id(value)
    if destination.exists():
        if read(destination) != value:
            raise BusinessInputError(
                "profile_identity_changed",
                str(destination),
                "existing binding differs; retain it and use a new instance",
            )
        return file_ref(destination)
    write(destination, value)
    return file_ref(destination)

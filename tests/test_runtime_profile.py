"""Validate real profile documents, identities, projections and named budgets."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from chip_evolve.core import toolchain
from chip_evolve.core.config import write
from chip_evolve.core.contracts import BusinessInputError
from chip_evolve.core.resources import CapacitySnapshot, preset, require_capacity, resolve_budget


@pytest.fixture
def bound_profile(tmp_path, monkeypatch):
    (tmp_path / "SOURCE_MANIFEST.json").write_text("{}\n")
    image = tmp_path / "image.sif"
    image.write_bytes(b"unit image bytes")
    plugin = tmp_path / "plugins/openroad-data/openroad-data.plugin.json"
    plugin.parent.mkdir(parents=True)
    write(
        plugin,
        {
            "environment": {"EDA_ORFS_IMAGE": str(image)},
            "adapter_entry": [
                str(tmp_path / "toolkits/.venv/bin/python"),
                "-m",
                "eda_toolkits.openroad.adapter",
            ],
        },
    )
    plugin.with_name("provenance.json").write_text("{}\n")
    installed = tmp_path / "installed.py"
    installed.write_text("# installed module\n")
    identity = {
        "distribution": "eda-toolkits",
        "version": "unit-1",
        "files": [
            {
                **toolchain.ref_payload(toolchain.file_ref(installed)),
                "relative_path": "eda_toolkits/__init__.py",
            }
        ],
    }
    monkeypatch.setattr(toolchain, "toolkit_identity", lambda python: identity)

    def output(command, **kwargs):
        if command[-2:] == ["uname", "-m"]:
            return toolchain.platform.machine() + "\n"
        assert command[-2] == "sha256sum"
        return "a" * 64 + "  " + command[-1] + "\n"

    monkeypatch.setattr(toolchain.subprocess, "check_output", output)
    monkeypatch.setattr(
        toolchain.subprocess, "run", lambda command, **kw: SimpleNamespace(returncode=0)
    )
    config = {"state_root": str(tmp_path), "orfs_image": str(image)}
    reference = toolchain.bind_runtime_profile(tmp_path, config)
    value = {
        "runtime_profile": toolchain.ref_payload(reference),
        "runtime": {"image": str(image)},
        "tools": {
            name: toolchain.layout_paths()[name] for name in ["openroad", "yosys"]
        },
    }
    deployment = SimpleNamespace(value=value)
    return deployment, config, reference


def test_profile_identity_projections_and_idempotent_binding(bound_profile, tmp_path):
    deployment, config, reference = bound_profile
    before = reference.path.read_bytes()
    loaded = toolchain.load_runtime_profile(deployment)
    assert loaded.origin == reference
    assert loaded.layout["flow_root"] == toolchain.layout_paths()["flow_root"]
    assert toolchain.bind_runtime_profile(tmp_path, config) == reference
    assert reference.path.read_bytes() == before
    deployment.value["tools"]["yosys"] = "/wrong/yosys"
    with pytest.raises(BusinessInputError, match="profile_projection_changed"):
        toolchain.load_runtime_profile(deployment)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "bad"),
        ("toolkit", None),
        ("binaries", {}),
        ("architecture", "wrong-host"),
        ("layout", {}),
    ],
)
def test_profile_corruption_refused_as_explicit_boundary_error(
    bound_profile, field, value
):
    deployment, _, reference = bound_profile
    wire = json.loads(reference.path.read_text())
    wire[field] = value
    wire["profile_id"] = toolchain.profile_id(wire)
    write(reference.path, wire)
    deployment.value["runtime_profile"] = toolchain.ref_payload(
        toolchain.file_ref(reference.path)
    )
    with pytest.raises(BusinessInputError):
        toolchain.load_runtime_profile(deployment)


def test_profile_raw_sha_and_image_sha_are_independent(bound_profile):
    deployment, config, reference = bound_profile
    reference.path.write_bytes(reference.path.read_bytes() + b" ")
    with pytest.raises(BusinessInputError, match="profile_identity_changed"):
        toolchain.load_runtime_profile(deployment)
    deployment.value["runtime_profile"] = toolchain.ref_payload(
        toolchain.file_ref(reference.path)
    )
    Path(config["orfs_image"]).write_bytes(b"changed image")
    with pytest.raises(BusinessInputError, match="profile_identity_changed"):
        toolchain.load_runtime_profile(deployment)


@pytest.mark.parametrize(
    "value", [None, True, 0, -1, float("nan"), float("inf"), float("-inf"), "8", 1.5]
)
def test_bad_explicit_resource_values_refused(value):
    # None means use the named preset and is covered separately.
    if value is None:
        assert resolve_budget("orfs").limits.memory_bytes == 24 << 30
    else:
        with pytest.raises(BusinessInputError, match="invalid_resource"):
            resolve_budget("orfs", memory_gib=value)


def test_named_build_budget_and_capacity_boundary_keep_real_requirements():
    build = resolve_budget("code-build")
    assert (
        build.limits.cpu_cores,
        build.limits.memory_bytes,
        build.limits.processes,
        build.native_threads,
    ) == (8, 64 << 30, 2048, 8)
    assert preset("code-build")["lto_workers"] == 1
    with pytest.raises(BusinessInputError, match="unqualified_build_budget"):
        resolve_budget("code-variant", memory_gib=24)
    exact = CapacitySnapshot(
        "http://unit", 8, 64 << 30, "public_resources", None, "unit"
    )
    require_capacity(build, exact)
    with pytest.raises(BusinessInputError, match="capacity_exceeded"):
        require_capacity(
            build,
            CapacitySnapshot(
                "http://unit", 8, 24 << 30, "public_resources", None, "unit"
            ),
        )

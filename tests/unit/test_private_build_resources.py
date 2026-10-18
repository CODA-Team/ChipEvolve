"""Private component/relink reservations must not shrink whole-toolchain builds."""

from copy import deepcopy

import pytest

from goalevolve.platform.execution import task_for


def profile():
    return {
        "experiment_id": "resource-qualification",
        "design": "arbitrary-design",
        "client_python": "python",
        "profile_path": "profile.json",
        "deadline_epoch": 9999999999,
        "resources": {
            "build": {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048},
            "physical": {"cpu_cores": 8, "memory_bytes": 24 << 30},
            "analysis": {"cpu_cores": 1, "memory_bytes": 4 << 30},
        },
    }


@pytest.mark.parametrize("component", ["rsz", "rmp", "grt", "cut"])
@pytest.mark.parametrize("relative", [False, True])
def test_component_rebuild_optional_resource_changes_only_reservation(
    tmp_path, component, relative
):
    p = profile()
    build = tmp_path / "build"
    target = build / "src" / component / "src"
    command = [
        "make",
        "-C",
        str(target.relative_to(build) if relative else target),
        "-B",
        "-j8",
    ]
    request = {
        "operation": "build",
        "command": command,
        "cwd": str(build),
        "build": str(build),
        "policy": {"timeout_s": 7200},
    }
    before = deepcopy(request)
    old = task_for(p, request, tmp_path / "request.json", "same-native-command")
    p["resources"]["variant_build"] = {
        "cpu_cores": 8,
        "memory_bytes": 16 << 30,
        "processes": 2048,
    }
    new = task_for(p, request, tmp_path / "request.json", "same-native-command")
    assert old["resources"]["memory_bytes"] == 64 << 30
    assert new["resources"]["memory_bytes"] == 16 << 30
    assert {k: v for k, v in old.items() if k != "resources"} == {
        k: v for k, v in new.items() if k != "resources"
    }
    assert request == before
    assert new["timeout_seconds"] == 7260 and new["max_attempts"] == 1


@pytest.mark.parametrize("memory_gib", [16, 96])
def test_explicit_relink_budget_is_optional_and_not_clamped(tmp_path, memory_gib):
    p = profile()
    request = {
        "operation": "build",
        "command": [
            "cmake",
            "-E",
            "cmake_link_script",
            "/frozen/link.txt",
            "--verbose",
        ],
        "policy": {"timeout_s": 7200},
    }
    assert (
        task_for(p, request, tmp_path / "request.json", "relink")["resources"]
        == p["resources"]["build"]
    )
    p["resources"]["variant_build"] = {"cpu_cores": 8, "memory_bytes": memory_gib << 30}
    assert (
        task_for(p, request, tmp_path / "request.json", "relink")["resources"]
        == p["resources"]["variant_build"]
    )


@pytest.mark.parametrize(
    "case",
    [
        "whole_make",
        "full_cmake",
        "other_component",
        "external_component",
        "no_force",
        "legacy",
    ],
)
def test_other_builds_keep_original_large_reservation(tmp_path, case):
    p = profile()
    p["resources"]["variant_build"] = {"cpu_cores": 8, "memory_bytes": 16 << 30}
    build = tmp_path / "build"
    commands = {
        "whole_make": ["make", "-C", str(build), "-B", "-j8"],
        "full_cmake": ["cmake", "--build", str(build), "--parallel", "8"],
        "other_component": ["make", "-C", str(build / "src/odb"), "-B", "-j8"],
        "external_component": [
            "make",
            "-C",
            str(tmp_path / "other/src/rsz/src"),
            "-B",
            "-j8",
        ],
        "no_force": ["make", "-C", str(build / "src/rsz/src"), "-j8"],
        "legacy": [],
    }
    request = {
        "operation": "build",
        "command": commands[case],
        "build": str(build),
        "policy": {"timeout_s": 7200},
    }
    assert (
        task_for(p, request, tmp_path / "request.json", case)["resources"]
        == p["resources"]["build"]
    )


@pytest.mark.parametrize("operation", ["physical", "analysis"])
def test_non_build_requests_are_unchanged(tmp_path, operation):
    p = profile()
    p["resources"]["variant_build"] = {"cpu_cores": 8, "memory_bytes": 16 << 30}
    request = {
        "operation": operation,
        "command": ["cmake", "-E", "cmake_link_script", "link.txt"],
        "policy": {"timeout_s": 7200},
    }
    assert (
        task_for(p, request, tmp_path / "request.json", operation)["resources"]
        == p["resources"][operation]
    )

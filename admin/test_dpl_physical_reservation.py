"""DPL experiments carry deployment CPU and memory limits into native commands."""

import zipfile
from argparse import Namespace
from types import SimpleNamespace
from typing import cast

import pytest

from chip_evolve import dpl as professional
from chip_evolve.config import Deployment, write


@pytest.mark.parametrize(
    ("memory_gib", "explicit_python", "physical_cpu"),
    [(None, False, None), (8, True, 4)],
)
def test_dpl_reservation_reaches_frozen_profile(
    tmp_path, monkeypatch, memory_gib, explicit_python, physical_cpu
):
    template = tmp_path / "template.json"
    resources = {
        "build": {"memory_bytes": 32 << 30},
        "variant_build": {"memory_bytes": 8 << 30},
        "physical": {"memory_bytes": 24 << 30},
    }
    if physical_cpu is not None:
        resources["physical"]["cpu_cores"] = physical_cpu
    write(
        template,
        {
            "orfs_root": str(tmp_path / "original-orfs"),
            "state_root": str(tmp_path / "original-state"),
            "core_binary": str(tmp_path / "core/openroad"),
            "resources": resources,
            "container_environment": {},
        },
    )
    binding = {"source": str(tmp_path / "source"), "profile_template": str(template)}
    dpl_python = tmp_path / (
        "dpl-python" if explicit_python else "source/.venv/bin/python"
    )
    dpl_python.parent.mkdir(parents=True, exist_ok=True)
    dpl_python.touch()
    if explicit_python:
        binding["python"] = str(dpl_python)
    if memory_gib is not None:
        binding["physical_memory_gib"] = memory_gib
    deployment = SimpleNamespace(
        design=lambda _: {"platform": "asap7", "nickname": "gcd"},
        value={
            "professional": {"dpl": binding},
            "client_python": "/client/python",
            "kernel_url": "http://kernel",
            "data_url": "http://facts",
        },
    )
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    monkeypatch.setattr(professional, "freeze", lambda *a, **kw: None)
    monkeypatch.setattr("chip_evolve.dpl_case.prepare_case", lambda *a: "gcd_asap7")
    monkeypatch.setattr(professional.shutil, "copytree", lambda *a, **kw: None)
    monkeypatch.setattr(professional.subprocess, "run", lambda *a, **kw: None)
    monkeypatch.setattr(professional, "inventory", lambda *a: {})

    def archive(_source, target):
        with zipfile.ZipFile(target, "w") as stream:
            stream.writestr("flow/results/3_4_place_resized.odb", b"actual-stage")

    monkeypatch.setattr(professional, "flatten_archive", archive)
    profiles = []

    class BaselineReached(Exception):
        pass

    def capture(path, value):
        assert path == experiment / "profile.json"
        profiles.append(value)

    def run_baseline(command, _source, env, _folder, _seconds):
        assert command[1].endswith("/baseline/run_baseline.sh")
        assert command[command.index("--threads") + 1] == str(physical_cpu or 8)
        assert env["DPL_EVOLVE_PYTHON"] == str(dpl_python)
        raise BaselineReached

    monkeypatch.setattr(professional, "write", capture)
    monkeypatch.setattr(professional, "invoke", run_baseline)
    frame = {
        "flow_archive": "input.zip",
        "run_id": "parent",
        "snapshot_ids": {"opendb": "objects", "orfs": "metrics"},
    }
    with pytest.raises(BaselineReached):
        professional.run_dpl(
            cast(Deployment, deployment),
            Namespace(seconds=600, design="gcd", operation="evolve"),
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    profile = profiles[0]
    assert profile["resources"]["physical"] == {
        "cpu_cores": physical_cpu or 8,
        "memory_bytes": (memory_gib if memory_gib is not None else 24) << 30,
        "processes": 2048,
    }
    assert profile["resources"]["build"] == resources["build"]
    assert profile["resources"]["variant_build"] == resources["variant_build"]
    assert profile["data_context"]["parent_run_id"] == "parent"
    assert profile["client_python"] == "/client/python"

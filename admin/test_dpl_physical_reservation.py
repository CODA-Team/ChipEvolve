"""DPL experiments can reserve measured memory without changing build budgets."""

import zipfile
from argparse import Namespace
from types import SimpleNamespace
from typing import cast

import pytest

from chip_evolve import professional
from chip_evolve.config import Deployment, write


@pytest.mark.parametrize("memory_gib", [None, 8])
def test_dpl_reservation_reaches_frozen_profile(tmp_path, monkeypatch, memory_gib):
    template = tmp_path / "template.json"
    resources = {
        "build": {"memory_bytes": 32 << 30},
        "variant_build": {"memory_bytes": 8 << 30},
        "physical": {"memory_bytes": 24 << 30},
    }
    write(
        template,
        {
            "orfs_root": str(tmp_path / "original-orfs"),
            "state_root": str(tmp_path / "original-state"),
            "resources": resources,
            "container_environment": {},
        },
    )
    binding = {"source": str(tmp_path / "source"), "profile_template": str(template)}
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

    class ProfileReached(Exception):
        pass

    def capture(path, value):
        assert path == experiment / "profile.json"
        profiles.append(value)
        raise ProfileReached

    monkeypatch.setattr(professional, "write", capture)
    frame = {
        "flow_archive": "input.zip",
        "run_id": "parent",
        "snapshot_ids": {"opendb": "objects", "orfs": "metrics"},
    }
    with pytest.raises(ProfileReached):
        professional.run_dpl(
            cast(Deployment, deployment),
            Namespace(seconds=600, design="gcd"),
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    profile = profiles[0]
    assert profile["resources"]["physical"] == {
        "cpu_cores": 8,
        "memory_bytes": (memory_gib if memory_gib is not None else 24) << 30,
        "processes": 2048,
    }
    assert profile["resources"]["build"] == resources["build"]
    assert profile["resources"]["variant_build"] == resources["variant_build"]
    assert profile["data_context"]["parent_run_id"] == "parent"

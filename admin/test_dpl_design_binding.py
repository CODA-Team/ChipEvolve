"""Native DPL problems follow actual designs without changing research rules."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chip_evolve.config import read
from chip_evolve.dpl_case import prepare_case


@pytest.mark.parametrize("name", ["gcd", "aes", "jpeg", "new_accelerator"])
def test_native_registry_resolves_bound_design_and_preserves_algorithm(tmp_path, name):
    controller = tmp_path / "controller"
    template = controller / "problems/gcd_asap7/problem.yaml"
    template.parent.mkdir(parents=True)
    algorithm = (
        "task_type: design_specific_legalizer_evolution\n"
        "objective:\n  primary: legalization_hpwl\n"
        "  guardrails:\n    - legality\n    - runtime\n"
        "patch_surface:\n  - tools/OpenROAD/src/dpl_evolve/src/StudentAlgorithm.cpp\n"
    )
    template.write_text(
        "name: gcd_asap7_legalizer_wl\ndesign: gcd\nplatform: asap7\n"
        "design_config: ./designs/asap7/gcd/config.mk\n" + algorithm
    )
    registry = controller / "scripts/repo/case_registry.py"
    registry.parent.mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "dplevolve/scripts/repo/case_registry.py",
        registry,
    )
    case = prepare_case(
        controller,
        {
            "nickname": name,
            "platform": "asap7",
            "dpl_case": "gcd_asap7",
            "orfs_config": f"designs/asap7/{name}/config.mk",
        },
    )
    problem = controller / "problems" / case / "problem.yaml"
    assert problem.read_text().endswith(algorithm)
    for field, expected in [
        ("design", name),
        ("platform", "asap7"),
        ("design_config", f"./designs/asap7/{name}/config.mk"),
    ]:
        actual = subprocess.check_output(
            [sys.executable, str(registry), "--case", case, "--field", field], text=True
        ).strip()
        assert actual == expected
    binding = read(tmp_path / "dpl-case-binding.json")
    assert binding["case_id"] == case
    assert binding["template_case"] == "gcd_asap7"
    assert binding["design"] == name

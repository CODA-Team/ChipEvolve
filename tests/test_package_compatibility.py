"""Compatibility resolves one physical owner, including fresh-process runners."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("order", ["legacy-first", "canonical-first", "from-import"])
def test_all_49_legacy_modules_and_exports_keep_object_identity(order, tmp_path):
    program = """import importlib,json
from chip_evolve._compat import ALIASES
pairs = dict(ALIASES, comparisons='chip_evolve.workflow.comparisons', continuation='chip_evolve.workflow.continuation')
assert len(pairs) == 49
for name, canonical in pairs.items():
 legacy='chip_evolve.'+name
 if ORDER=='canonical-first':
  new=importlib.import_module(canonical); old=importlib.import_module(legacy)
 elif ORDER=='from-import':
  ns={}; exec('from chip_evolve import '+name+' as value', ns); old=ns['value']; new=importlib.import_module(canonical)
 else:
  old=importlib.import_module(legacy); new=importlib.import_module(canonical)
 assert old is new, name
 for key,value in vars(new).items():
  if not key.startswith('_'): assert getattr(old,key) is value, (name,key)
 sentinel=object(); old.compatibility_probe=sentinel
 assert new.compatibility_probe is sentinel
 del new.compatibility_probe
from chip_evolve.workflow import native, goal, eco
for name,owner in [('run_goal',goal),('run_eco',eco),('goal_checkpoint_origin',goal),('latest_producer',goal),('goal_producer',goal),('restore_goal_checkpoint',goal)]:
 assert getattr(native,name) is getattr(owner,name),name
print(json.dumps({'legacy_modules':len(pairs),'order':ORDER,'identity':True}))
""".replace("ORDER", repr(order))
    result = subprocess.run(
        [sys.executable, "-E", "-s", "-c", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["legacy_modules"] == 49


@pytest.mark.parametrize("module", ["comparisons", "continuation"])
def test_legacy_module_runners_preserve_help_without_warnings(module):
    outputs = []
    commands = [
        [sys.executable, "-E", "-s", "-m", "chip_evolve." + module, "--help"],
        [
            sys.executable,
            "-E",
            "-s",
            "-c",
            "import sys; from chip_evolve.workflow import "
            + module
            + "; sys.argv=['"
            + module
            + ".py','--help']; "
            + module
            + ".main()",
        ],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert result.stderr == b""
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]


def test_workspace_owner_is_independent_of_caller_cwd(tmp_path):
    from chip_evolve.core.config import workspace_root
    from chip_evolve.core.jobs import ROOT as jobs_root

    previous = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert jobs_root == workspace_root() == ROOT
        assert (jobs_root / "chip-evolve.py").is_file()
    finally:
        os.chdir(previous)

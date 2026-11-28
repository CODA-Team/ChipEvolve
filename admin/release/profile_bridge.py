"""Fixed stdlib bridge to root profile APIs through an installed client environment."""

import json
import os
import subprocess
from pathlib import Path

PROGRAM = """import json,sys
from pathlib import Path
from chip_evolve.core.toolchain import bind_runtime_profile,layout_paths,ref_payload
from chip_evolve.core.resources import preset,startup_receipt,resolve_budget,admit_task
from chip_evolve.core.config import Deployment
from openroad_platform_client import KernelClient
p=json.load(sys.stdin)
if p['operation']=='layout': r=layout_paths()
elif p['operation']=='preset': r=preset(p['kind'])
elif p['operation']=='bind': r=ref_payload(bind_runtime_profile(Path(p['workspace']),p['config']))
elif p['operation']=='startup': r=ref_payload(startup_receipt(Path(p['workspace']),p['config'],p['record'],p['health']))
elif p['operation']=='admit-build':
 d=Deployment(Path(p['deployment'])); b=resolve_budget('code-build',memory_gib=p['memory_gib']); admit_task(d,KernelClient(d.value['kernel_url']),b); r={'admitted':True,'memory_bytes':b.limits.memory_bytes,'cpu_cores':b.limits.cpu_cores}
else: raise ValueError('Unsupported profile bridge operation')
print(json.dumps(r))
"""


def invoke(workspace, operation, **payload):
    if operation not in {"layout", "preset", "bind", "startup", "admit-build"}:
        raise ValueError("Unsupported profile bridge operation")
    root = Path(workspace).resolve()
    python = root / "agent/query-agent/.venv/bin/python"
    if not python.is_file() or not (root / "chip-evolve.py").is_file():
        raise FileNotFoundError("Bootstrap the declared ChipEvolve workspace first")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"}
    }
    environment["PYTHONNOUSERSITE"] = "1"
    return json.loads(
        subprocess.check_output(
            [str(python), "-c", PROGRAM],
            input=json.dumps(
                {"operation": operation, "workspace": str(root), **payload}
            ),
            cwd=root,
            env=environment,
            text=True,
        )
    )

"""OpenROAD launcher for an explicitly configured, immutable ORFS image."""
import os
from pathlib import Path
import shutil
import sys


def main() -> int:
    image = os.environ.get('EDA_ORFS_IMAGE')
    runtime = shutil.which(os.environ.get('EDA_CONTAINER_RUNTIME','apptainer'))
    if not image or not Path(image).is_file() or not runtime:
        raise SystemExit('Set EDA_ORFS_IMAGE to an ORFS SIF and install apptainer')
    workspace = Path.cwd().resolve()
    args = ['/work/' + arg[len(str(workspace))+1:] if arg.startswith(str(workspace)+'/') else arg
            for arg in sys.argv[1:]]
    os.execv(runtime, [runtime,'exec','--cleanenv','--containall','--bind',str(workspace)+':/work',
                       '--pwd','/work',str(Path(image).resolve()),
                       '/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad',*args])
    return 0

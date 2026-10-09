"""Build identifiable development wheels without replacing running venvs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    a.output=a.output.resolve();a.output.mkdir(exist_ok=False)
    packages=[root/'execution-foundation'/n for n in
              ('contracts','core/client','core/runtime','core/registry','core/evaluator','core/provenance','gateway')]
    packages.extend(root/n for n in ('toolkits','data-foundation','data-interface','query-agent'))
    env=dict(os.environ,PYTHONNOUSERSITE='1',PIP_DISABLE_PIP_VERSION_CHECK='1')
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(key,None)
    receipts=[]
    for path in packages:
        command=[sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(a.output),str(path)]
        subprocess.run(command,env=env,check=True)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
        receipts.append({'source':str(path),'commit':commit,'command':command})
    hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(a.output.glob('*.whl'))}
    (a.output/'manifest.json').write_text(json.dumps({'wheels':hashes,'builds':receipts},indent=2)+'\n')
    print(json.dumps({'built_wheels':len(hashes),'destination':str(a.output)}))


if __name__=='__main__':main()

"""Install published wheels into five isolated environments, without editable links."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


PACKAGES={
 'execution-foundation':['openroad-platform-'+p for p in ('contracts','client','runtime','registry','evaluator','provenance','gateway')],
 'data-foundation':['openroad-app-data-foundation'],
 'data-interface':['eda-ai-client'],
 'toolkits':['eda-toolkits'],
 'query-agent':['agentic-eda-query-agent'],
}
CHECKS={
 'execution-foundation':['mypy==2.4.0','black==26.10.0'],
 'query-agent':['pyright==1.1.414','import-linter==2.15'],
 'data-foundation':['openroad-platform-runtime'],
 'toolkits':['openroad-platform-runtime'],
}


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--packages',type=Path,required=True)
    p.add_argument('--dependencies',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();a.workspace=a.workspace.resolve();a.evidence=a.evidence.resolve()
    a.evidence.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((a.packages/'manifest.json').read_text())
    for name,expected in manifest['wheels'].items():
        assert hashlib.sha256((a.packages/name).read_bytes()).hexdigest()==expected, 'wheel digest differs: '+name
    env=dict(os.environ,PYTHONNOUSERSITE='1',PIP_DISABLE_PIP_VERSION_CHECK='1',
             NO_PROXY='localhost,127.0.0.1,::1',no_proxy='localhost,127.0.0.1,::1')
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CONDA_PREFIX'):env.pop(key,None)
    started=time.monotonic();records=[]
    with (a.evidence/'terminal.log').open('w') as terminal:
        for project,distributions in PACKAGES.items():
            directory=a.workspace/project;assert (directory/'.git').is_dir()
            venv=directory/'.venv';assert not venv.exists(), 'installation requires a clean venv destination'
            subprocess.run([sys.executable,'-m','venv',str(venv)],env=env,check=True,stdout=terminal,stderr=subprocess.STDOUT)
            python=venv/'bin/python'
            install=[str(python),'-m','pip','install','--pre','--no-index',
              '--find-links',str(a.packages.resolve()),'--find-links',str(a.dependencies.resolve()),
              'setuptools==84.0.0','wheel==0.48.0','pytest==9.1.1','ruff==0.16.8',
              *distributions,*CHECKS.get(project,[])]
            terminal.write(json.dumps(install)+'\n');terminal.flush()
            subprocess.run(install,env=env,check=True,stdout=terminal,stderr=subprocess.STDOUT)
            subprocess.run([str(python),'-m','pip','check'],env=env,check=True,stdout=terminal,stderr=subprocess.STDOUT)
            lock=subprocess.check_output([str(python),'-m','pip','freeze','--all'],env=env,text=True)
            assert '-e ' not in lock and 'file://' not in lock, 'source checkout dependency leaked into installed environment'
            (a.evidence/(project+'-environment.lock.txt')).write_text(lock)
            (directory/'environment.lock.txt').write_text(lock)
            inspect=json.loads(subprocess.check_output([str(python),'-m','pip','inspect'],env=env,text=True))
            (a.evidence/(project+'-pip-inspect.json')).write_text(json.dumps(inspect,indent=2)+'\n')
            commits=subprocess.check_output(['git','rev-parse','HEAD'],cwd=directory,text=True).strip()
            records.append({'project':project,'commit':commits,'python':str(python),
                            'installed_distributions':distributions,'editable_dependencies':False})
    result={'installed':records,'seconds':time.monotonic()-started,'wheel_hashes':manifest['wheels'],
            'runtime_source_dependencies':False,'validation':'Installation only; service/business replay is a separate acceptance.'}
    (a.evidence/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()

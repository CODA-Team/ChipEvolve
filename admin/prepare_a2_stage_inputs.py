"""Bind a staged candidate to a frozen native source and its tool profile."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--slot', type=int, default=1)
    parser.add_argument('--checkpoint-stage', choices=['place', 'cts', 'final'])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new output directory.')
    flow = args.native_run.resolve() / 'source/flow'
    args.output.mkdir(parents=True)
    tools = Path('/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install')
    profile = {'flow_dir': str(flow),
               'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=flow, text=True).strip(),
               'makefile_sha256': digest(flow / 'Makefile'),
               'eval_tns_sha256': digest(flow / 'eval_tns.tcl'),
               'openroad_bin': str(tools / 'OpenROAD/bin/openroad'),
               'yosys_bin': str(tools / 'yosys/bin/yosys'),
               'python_bin': str(ROOT / 'flow-agent/.venv/bin/python')}
    (args.output / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    design = flow / 'designs/nangate45/aes'
    shutil.copy2(design / f'config_{args.slot}.mk', args.output / 'candidate.mk')
    shutil.copy2(design / f'constraint_{args.slot}.sdc', args.output / 'candidate.sdc')
    if args.checkpoint_stage:
        limit = {'place': 3, 'cts': 4, 'final': 6}[args.checkpoint_stage]
        stem = {'place': '3_place', 'cts': '4_cts', 'final': '6_final'}[args.checkpoint_stage]
        relative = Path(f'nangate45/aes/run_{args.slot}')
        anchor = flow / 'results' / relative / f'{stem}.odb'
        if not anchor.is_file() or anchor.stat().st_size == 0:
            raise ValueError('Native checkpoint is missing: ' + str(anchor))
        with zipfile.ZipFile(args.output / 'checkpoint.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ('results', 'logs', 'objects', 'reports'):
                for path in sorted((flow / name / relative).rglob('*')):
                    if not path.is_file():
                        continue
                    prefix = path.name.split('_', 1)[0]
                    if name != 'objects' and prefix.isdigit() and int(prefix) > limit:
                        continue
                    archive.write(path, 'flow/' + name + '/' + str(path.relative_to(flow / name / relative)))
    (args.output / 'input-bindings.json').write_text(json.dumps({
        'native_run': str(args.native_run.resolve()), 'candidate_slot': args.slot,
        'checkpoint_stage': args.checkpoint_stage, 'files': {
            path.name: {'sha256': digest(path), 'size_bytes': path.stat().st_size}
            for path in args.output.iterdir() if path.is_file()}}, indent=2) + '\n')


if __name__ == '__main__':
    main()

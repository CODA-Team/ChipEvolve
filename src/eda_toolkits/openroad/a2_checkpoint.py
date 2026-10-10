"""Restore only native stage state into an isolated attempt."""
from pathlib import Path
import shutil
import stat
import zipfile


def restore_checkpoint(archive_path, destination):
    destination.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        names = set()
        for entry in archive.infolist():
            path = Path(entry.filename)
            if path.parts and path.parts[0] == 'flow':
                path = Path(*path.parts[1:])
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] not in {'results', 'logs', 'objects', 'reports', 'combined.log'}):
                raise ValueError('checkpoint member is outside the native output tree: ' + entry.filename)
            if path.parts[0] == 'combined.log' and len(path.parts) != 1:
                raise ValueError('combined.log must be a file')
            if stat.S_ISLNK(entry.external_attr >> 16) or path.as_posix() in names:
                raise ValueError('checkpoint contains a link or duplicate path: ' + entry.filename)
            names.add(path.as_posix())
            output = destination / path
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, output.open('wb') as target:
                    shutil.copyfileobj(source, target)


def required_checkpoint(flow, stage):
    stems = {'cts': '3_place', 'route_finish': '4_cts', 'eval_place': '3_place',
             'eval_cts': '4_cts', 'eval_final': '6_final'}
    stem = stems[stage]
    extensions = ('odb',) if stage.startswith('eval_') else ('odb', 'sdc')
    paths = [flow / 'results' / f'{stem}.{extension}' for extension in extensions]
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('native predecessor is missing or empty: ' + path.name)
    return paths


def clear_downstream(flow, stage):
    prefixes = {'cts': ('4_', '5_', '6_'), 'route_finish': ('5_', '6_')}[stage]
    for directory in ('results', 'logs', 'reports'):
        for path in (flow / directory).glob('*'):
            if path.is_file() and path.name.startswith(prefixes):
                path.unlink()

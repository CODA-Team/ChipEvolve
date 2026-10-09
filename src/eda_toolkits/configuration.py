"""Materialize execution manifests, referencing this installed environment."""
from importlib.resources import files
import json
from pathlib import Path
import sys


def configure_plugins(output: Path, *, image: str | None = None, activity_lock: str | None = None) -> dict:
    destination = output / 'openroad-data'
    destination.mkdir(parents=True, exist_ok=True)
    resource = files('eda_toolkits.openroad')
    manifest = json.loads(resource.joinpath('openroad-data.plugin.json').read_text())
    manifest['adapter_entry'] = [sys.executable, '-m', 'eda_toolkits.openroad.adapter']
    existing = destination / 'openroad-data.plugin.json'
    if image is None and existing.is_file():
        configured = json.loads(existing.read_text()).get('environment', {})
        image = configured.get('EDA_ORFS_IMAGE')
        activity_lock = activity_lock or configured.get('EDA_ACTIVITY_LOCK')
    if image is not None:
        if not Path(image).is_file():
            raise ValueError('configured ORFS image does not exist')
        manifest['environment'] = {'EDA_ORFS_IMAGE':str(Path(image).resolve())}
    lease = Path(activity_lock).resolve() if activity_lock else output.resolve().parent / 'eda-activity.lock'
    manifest.setdefault('environment', {})['EDA_ACTIVITY_LOCK'] = str(lease)
    (destination / 'openroad-data.plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (destination / 'provenance.json').write_text(resource.joinpath('provenance.json').read_text())
    return {'plugin_root': str(output.resolve()), 'python': sys.executable,
            'adapter_entry': manifest['adapter_entry'], 'plugin_version': manifest['plugin_version']}

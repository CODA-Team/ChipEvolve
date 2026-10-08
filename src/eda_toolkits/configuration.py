"""Materialize execution manifests, referencing this installed environment."""
from importlib.resources import files
import json
from pathlib import Path
import sys


def configure_plugins(output: Path) -> dict:
    destination = output / 'openroad-data'
    destination.mkdir(parents=True, exist_ok=True)
    resource = files('eda_toolkits.openroad')
    manifest = json.loads(resource.joinpath('openroad-data.plugin.json').read_text())
    manifest['adapter_entry'] = [sys.executable, '-m', 'eda_toolkits.openroad.adapter']
    (destination / 'openroad-data.plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (destination / 'provenance.json').write_text(resource.joinpath('provenance.json').read_text())
    return {'plugin_root': str(output.resolve()), 'python': sys.executable,
            'adapter_entry': manifest['adapter_entry'], 'plugin_version': manifest['plugin_version']}

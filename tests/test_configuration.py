"""Repeated environment setup preserves explicit tool identity."""
import json
import pytest
from eda_toolkits.configuration import configure_plugins


def test_reconfiguration_keeps_image_and_missing_image_is_explicit(tmp_path):
    image = tmp_path / 'tool.sif'
    image.write_bytes(b'image')
    plugins = tmp_path / 'plugins'
    configure_plugins(plugins, image=str(image))
    configure_plugins(plugins)
    manifest = plugins / 'openroad-data/openroad-data.plugin.json'
    environment = json.loads(manifest.read_text())['environment']
    assert environment['EDA_ORFS_IMAGE'] == str(image)
    assert environment['EDA_ACTIVITY_LOCK'] == str(tmp_path / 'eda-activity.lock')
    image.unlink()
    with pytest.raises(ValueError, match='does not exist'):
        configure_plugins(plugins)

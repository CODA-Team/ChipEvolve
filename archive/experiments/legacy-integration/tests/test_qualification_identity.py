"""Gold must follow imported bytes, even when newer or altered bundles exist."""
import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from qualification.runners.dataset import resolve, served_artifact


def make_bundle(root, run, value):
    directory = root / 'runtime-workspaces' / run / 'stage-main' / 'attempt-1'
    data = directory / 'query-data'
    data.mkdir(parents=True)
    (data / 'manifest.json').write_text(json.dumps({'snapshot_id': 'test'}))
    (data / 'objects.jsonl').write_text(json.dumps({'value': value}) + '\n')
    archive = directory / 'query-data.zip'
    with zipfile.ZipFile(archive, 'w') as zipped:
        for file in data.iterdir():
            zipped.write(file, file.name)
    return data, {'artifact_id': 'art-' + run, 'run_id': run, 'attempt_id': 'attempt-id',
                  'logical_path': 'query-data.zip',
                  'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'category': 'data_snapshot'}


def test_gold_never_substitutes_newer_bundle(tmp_path):
    original, source = make_bundle(tmp_path, 'run-old', 1)
    make_bundle(tmp_path, 'run-new', 2)
    assert resolve(tmp_path, 'test', served=source).directory == original
    original.parent.joinpath('query-data.zip').unlink()
    with pytest.raises(LookupError, match='no local archive matches'):
        resolve(tmp_path, 'test', served=source)


def test_gold_rejects_altered_archive_or_expanded_member(tmp_path):
    directory, source = make_bundle(tmp_path, 'run-old', 1)
    directory.joinpath('objects.jsonl').write_text('{"value": 2}\n')
    with pytest.raises(LookupError, match='differs from imported artifact'):
        resolve(tmp_path, 'test', served=source)
    archive = directory.parent / 'query-data.zip'
    archive.write_bytes(archive.read_bytes() + b'changed')
    with pytest.raises(LookupError, match='no local archive matches'):
        resolve(tmp_path, 'test', served=source)


def test_imported_identity_is_required(tmp_path):
    _, source = make_bundle(tmp_path, 'run-old', 1)
    client = SimpleNamespace(get_stage_summary=lambda _: {
        'data': {'snapshot': {'source_artifacts': [source]}}})
    assert served_artifact(client, 'test')['artifact_id'] == source['artifact_id']
    del source['sha256']
    with pytest.raises(LookupError, match='lacks sha256'):
        served_artifact(client, 'test')


def test_gold_rejects_extra_expanded_file(tmp_path):
    directory, source = make_bundle(tmp_path, 'run-old', 1)
    directory.joinpath('observations.jsonl').write_text('{"value": 99}\n')
    with pytest.raises(LookupError, match='file set differs'):
        resolve(tmp_path, 'test', served=source)

"""Independent verification must keep native names and fail on a missing fact."""
import hashlib
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

CHECK = run_path(str(Path(__file__).parents[1] / 'evidence/B/check_object_facts_against_odb.py'))
DEF = r'''COMPONENTS 1 ;
    - u CELL + PLACED ( 10 20 ) N ;
END COMPONENTS
NETS 1 ;
    - reg\[1\] ( u Q ) ( v A ) + ROUTED metal1 ( 30 40 ) ;
END NETS
'''


def test_native_net_name_and_connections_are_preserved():
    components, nets = CHECK['parse_def'](DEF)
    assert components == {'u': ('CELL', 10, 20, 'R0')}
    assert nets == {r'reg\[1\]': 2}


def test_missing_net_or_wrong_odb_cannot_pass(tmp_path, monkeypatch):
    odb = tmp_path / 'design.odb'
    odb.write_bytes(b'original ODB')
    source = {'artifact_id': 'art-1', 'category': 'raw_design_database',
              'sha256': hashlib.sha256(odb.read_bytes()).hexdigest()}
    client = SimpleNamespace(
        get_stage_summary=lambda _: {'data': {'snapshot': {'source_artifacts': [source]}}},
        get_instance=lambda *_: {'status': 'available', 'instance': {'attributes': {
            'master': 'CELL', 'orientation': 'R0'}}, 'physical_context': [
                {'bbox': {'x_min': 10, 'y_min': 20}}]},
        get_net_context=lambda *_: {'data': {'entities': []}})
    state = CHECK['main'].__globals__
    monkeypatch.setitem(state, 'EdaAiClient', lambda _: client)
    monkeypatch.setitem(state, 'DUMP', tmp_path)
    monkeypatch.setitem(state, 'export_def', lambda _, target: target.write_text(DEF))
    monkeypatch.setattr('sys.argv', ['check', '--snapshot', 'test', '--odb', str(odb)])
    assert CHECK['main']() == 1
    client.get_net_context = lambda *_: {'data': {'entities': [
        {'kind': 'net', 'attributes': {'fanout': 1}}]}}
    assert CHECK['main']() == 0
    odb.write_bytes(b'another ODB')
    with pytest.raises(SystemExit, match='ODB hash differs'):
        CHECK['main']()

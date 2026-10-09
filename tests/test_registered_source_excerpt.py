"""Excerpt delivery preserves registered identity, evidence and bounded coverage."""
from types import SimpleNamespace

import pytest

from openroad_app_data_foundation.envelope import envelope
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.mark.parametrize('mismatch', [None, 'sha256', 'size_bytes'])
def test_registered_source_identity_and_paging(tmp_path, mismatch):
    ref={'artifact_id':'art-source','run_id':'run-source','sha256':'a'*64,
         'size_bytes':30,'logical_path':'area.rpt','category':'analysis_report','stage':'main'}
    store=DataStore(tmp_path/'facts.sqlite')
    store.register({'snapshot':{'snapshot_id':'s','design_id':'chip','revision_id':'r',
        'run_id':'run','stage':'finish','created_at':'2026-10-08', 'source_artifacts':[ref]}})
    excerpt={'artifact_id':'art-source','sha256':'a'*64,'size_bytes':30,
             'offset':0,'bytes_read':10,'text':'native area','truncated':True}
    if mismatch:excerpt[mismatch] = 'b'*64 if mismatch=='sha256' else 31
    def fetch(run_id, artifact_id, **query):
        assert run_id=='run-source' and artifact_id=='art-source'
        assert query=={'offset':0,'max_bytes':10}
        return excerpt
    handler=Handler.__new__(Handler)
    handler.store,handler.auto_import=store,False
    handler.execution_client=SimpleNamespace(artifact_excerpt=fetch)
    handler.archive_client=None
    path='/snapshots/s/sources/art-source/excerpt'
    try:
        if mismatch:
            with pytest.raises(ValueError,match='identity differs'):
                handler._get(path,{'max_bytes':'10'})
        else:
            result=envelope(path,{},handler._get(path,{'max_bytes':'10'}))
            assert result['status']=='truncated'
            assert result['tool']=='get_source_excerpt'
            assert result['evidence']==[ref]
            assert result['data']['excerpt']['next_offset']==10
    finally:store.close()

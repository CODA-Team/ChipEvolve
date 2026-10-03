"""Compact public native delivery must retain real output, failures and paging."""
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from openroad_app_data_foundation.native_queries import submit_native_query
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from tests.test_eda_engineering import sample


class NativeClient:
    def __init__(self, status):
        self.status, self.submissions, self.reads = status, [], []
        self.report = 'actual native result\nsecond original line\n'
        self.inputs = [{'kind': 'raw_library', 'artifact_id': 'lib-'+str(i),
                        'sha256': str(i)*64, 'metadata': {'source_field': 'libraries', 'original_path': '/original/lib'+str(i)}}
                       for i in range(8)]

    def submit(self, task):
        self.submissions.append(task)
        return {'run': {'run_id': 'native-job', 'status': 'queued',
                        'staged_inputs': [{'description': 'large input metadata'}]*100}}

    def run(self, run_id):
        assert run_id == 'native-job'
        return {'project_id': 'eda-ai-native-query', 'status': self.status,
                'labels': {'parent_snapshot_id': 's'},
                'terminal_reason': 'native_error' if self.status == 'failed' else None,
                'stages': [{'attempts': [{'failure': {'message': 'actual Tcl failure'}}]}] if self.status == 'failed' else []}

    def artifacts(self, run_id):
        return [*self.inputs, {'kind': 'analysis_report', 'artifact_id': 'output',
                              'sha256': 'a'*64, 'metadata': {'report': 'native'}}]

    def artifact_excerpt(self, run_id, artifact_id, *, offset, max_bytes):
        self.reads.append((offset,max_bytes))
        text = self.report[offset:offset+max_bytes]
        return {'text': text, 'bytes_read': len(text), 'offset': offset,
                'size_bytes': len(self.report), 'truncated': offset+len(text)<len(self.report)}


@pytest.fixture
def store(tmp_path):
    pack=sample()
    pack['run_summary']['timing_context']={'executor':'/tool/openroad'}
    pack['snapshot']['source_artifacts']=[{'artifact_id':'odb','category':'raw_design_database',
        'logical_path':'inputs/design.odb','run_id':'run','stage':'finish','sha256':'a'*64,'size_bytes':20}]
    db=DataStore(tmp_path/'native.sqlite');db.register(pack)
    yield db
    db.close()


def handler(store, client):
    h=Handler.__new__(Handler)
    h.store,h.execution_client,h.auto_import=store,client,False
    return h


@pytest.mark.parametrize('status', ['succeeded','failed','running','timed_out'])
def test_public_default_preserves_outcome_and_full_input_continuation(store,status):
    client=NativeClient(status);h=handler(store,client)
    compact=h._get('/native-queries/native-job', {'offset':'2','max_bytes':'7'})
    assert compact['status']==status and compact['run_id']=='native-job'
    assert 'original_input_artifacts' not in compact
    address=urlsplit(compact['delivery']['full_details'])
    query={k:v[0] for k,v in parse_qs(address.query).items()}
    full=h._get(address.path,query)
    assert client.submissions==[]
    if status=='running':
        assert 'excerpt' not in compact and 'excerpt' not in full
    else:
        assert compact['excerpt']==full['excerpt']
        assert compact['source']==full['source']
        assert full['original_input_artifacts']==client.inputs
        assert compact['excerpt']['next_offset']==9
        if status=='failed':
            assert compact['failure_details']==full['failure_details']==[{'message':'actual Tcl failure'}]
            assert compact['terminal_reason']=='native_error'
        next_page=h._get(address.path,{'offset':str(compact['excerpt']['next_offset']),'max_bytes':'65536'})
        assert compact['excerpt']['text']+next_page['excerpt']['text']==client.report[2:]
        assert next_page['excerpt']['next_offset'] is None


@pytest.mark.parametrize('detail', [None,'full'])
def test_public_submit_executes_identical_script_and_reads_actual_completion(store,detail):
    client=NativeClient('succeeded');h=handler(store,client)
    query={'script':'puts real_facts','wait_seconds':1,'max_bytes':65536}
    if detail: query['detail']=detail
    h.path='/snapshots/s/native-queries';h._read_body=lambda:dict(query)
    replies=[];h._send=lambda code,payload:replies.append((code,payload))
    h.do_POST()
    code,payload=replies[0]
    assert code==200 and len(client.submissions)==1
    assert client.submissions[0]['inputs']['script']=='puts real_facts'
    assert client.submissions[0]['staged_inputs']==[{'destination':'inputs/design.odb','artifact_id':'odb'}]
    assert payload['status']=='succeeded' and payload['excerpt']['text']==client.report
    if detail=='full':
        assert payload['original_input_artifacts']==client.inputs
        assert len(payload['run']['staged_inputs'])==100
    else:
        assert payload['run']=={'run_id':'native-job','status':'succeeded'}
        assert payload['delivery']['original_input_artifact_count']==8


def test_internal_consumers_keep_full_original_inputs_by_default(store):
    client=NativeClient('succeeded')
    result=submit_native_query(store,client,'s',{'script':'puts real_facts','wait_seconds':1})
    assert result['original_input_artifacts']==client.inputs
    assert len(result['run']['staged_inputs'])==100


def test_invalid_detail_is_rejected_before_submission_or_wait(store):
    client=NativeClient('running');h=handler(store,client)
    h.path='/snapshots/s/native-queries';h._read_body=lambda:{'script':'puts ok','detail':'bogus'}
    replies=[];h._send=lambda code,payload:replies.append((code,payload))
    h.do_POST()
    assert replies[0][0]==400 and client.submissions==[]
    with pytest.raises(ValueError,match='detail'):
        h._get('/native-queries/native-job',{'detail':'bogus','wait_seconds':'120'})
    assert client.reads==[]

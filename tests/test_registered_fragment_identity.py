"""Self-consistent cached JSON cannot impersonate a different registered original."""
import hashlib
import json

import pytest

from openroad_app_data_foundation.queries import read_evidence
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.mark.parametrize('registered_matches', [True, False])
def test_cached_fragment_must_match_registered_original(tmp_path, registered_matches):
    payload = json.dumps({'checks':[{'slack':-0.2,'endpoint':'out'}]}).encode()
    digest = hashlib.sha256(payload).hexdigest() if registered_matches else 'a'*64
    store = DataStore(tmp_path/'facts.sqlite')
    try:
        store.register({
            'snapshot':{'snapshot_id':'s','design_id':'gcd','revision_id':'r',
                        'run_id':'run','stage':'finish','created_at':'2026-01-01T00:00:00Z'},
            'timing_paths':[{'snapshot_id':'s','path_id':'p','slack':-0.2,
                            'evidence':[{'logical_path':'query-data/timing_report.json','sha256':digest,
                                         'detail':{'path_index':0}}]}],
            'fragment_sources':{'query-data/timing_report.json':payload},
        })
        result = read_evidence(store,'s','timing_paths','p')
        assert result['available'] == int(registered_matches)
        fragment = result['fragments'][0]
        if registered_matches:
            assert fragment['fragment'] == {'slack':-0.2,'endpoint':'out'}
            handler = object.__new__(Handler)
            handler.store = store
            route = '/snapshots/s/records/timing_paths/p/fragments'
            projected = handler._get(route, {'fields':'fragments.fragment.slack'})
            assert projected['fragments'][0]['fragment'] == {'slack':-0.2}
            assert projected['fragments'][0]['sha256'] == fragment['sha256']
            assert projected['available'] == result['available']
            assert projected['delivery']['full_details'] == route + '?detail=full'
            with pytest.raises(ValueError, match='available fields'):
                handler._get(route, {'fields':'fragments.fragment.data_path_increments'})
        else:
            assert fragment['status'] == 'unavailable'
            assert 'registered original digest' in fragment['reason']
            assert 'fragment' not in fragment
    finally:
        store.close()

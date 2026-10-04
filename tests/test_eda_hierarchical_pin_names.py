"""A native parent and a library pin can use different legal bus spellings."""
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.discovery import list_objects
from tests.test_eda_engineering import sample


def test_partly_escaped_hierarchical_pin_resolves_without_scanning(tmp_path):
    pack=sample()
    parent=r'group\[0\]/bank\[4\].ram'
    pack['entities'][0]['name']=parent
    pack['entities'].append({'object_id':'iterm:9','kind':'pin','name':parent+'/addr[0]',
        'parent_id':'i','attributes':{'direction':'INPUT'}})
    store=DataStore(tmp_path/'s.sqlite')
    try:
        store.register(pack)
        name='group[0]/bank[4].ram/addr[0]'
        rows=store.entities_named('s','pin',name)
        assert len(rows)==1 and rows[0]['object_id']=='iterm:9'
        result=list_objects(store,'s',{'kind':'pin','name':name})
        assert result['count']==1 and result['objects'][0]['object_id']=='iterm:9'
        assert store.entities_named('s','pin','group[0]/bank[5].ram/addr[0]')==[]
    finally:store.close()


def test_hierarchical_net_and_local_bus_can_have_independent_spelling(tmp_path):
    pack = sample()
    pack['entities'].extend([
        {'object_id': 'net:mixed', 'kind': 'net', 'name': r'group\[0\]/core\[3\]/events[0]'},
        {'object_id': 'net:other', 'kind': 'net', 'name': r'group\[0\]/core\[3\]/events[1]'}])
    store = DataStore(tmp_path / 's.sqlite')
    try:
        store.register(pack)
        for spelling in ('group[0]/core[3]/events[0]', r'group\[0\]/core\[3\]/events[0]',
                         r'group\[0\]/core\[3\]/events\[0\]'):
            rows = store.entities_named('s', 'net', spelling)
            assert [r['object_id'] for r in rows] == ['net:mixed']
        assert store.entities_named('s', 'net', 'group[0]/core[4]/events[0]') == []
        assert store.entities_named('s', 'net', 'group[0]/core[3]/events[2]') == []
        pack['entities'].append({'object_id': 'net:ambiguous', 'kind': 'net',
                                 'name': 'group[0]/core[3]/events[0]'})
        pack['snapshot']['snapshot_id'] = 's2'
        store.register(pack)
        assert {r['object_id'] for r in store.entities_named('s2', 'net', 'group[0]/core[3]/events[0]')} == {
            'net:mixed', 'net:ambiguous'}
    finally:
        store.close()

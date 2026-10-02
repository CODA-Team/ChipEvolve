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

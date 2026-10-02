"""Distinct receiving instances, ports and directional pin filtering."""
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.discovery import list_objects
from openroad_app_data_foundation.engineering import object_statistics
from tests.test_eda_engineering import sample


def test_net_roles_join_distinct_parents_and_filter_pin_direction(tmp_path):
    pack=sample()
    pack['entities'] += [
        {'object_id':'a','kind':'pin','name':'u/A','parent_id':'i','attributes':{'direction':'INPUT'}},
        {'object_id':'b','kind':'pin','name':'u/B','parent_id':'i','attributes':{'direction':'INPUT'}},
        {'object_id':'z','kind':'pin','name':'clock_buf/Z','parent_id':'c','attributes':{'direction':'OUTPUT'}},
        {'object_id':'port','kind':'pin','name':'OUT','parent_id':None,'attributes':{'direction':'OUTPUT'}}]
    pack['relations']=[{'relation_id':'r'+str(j),'subject_id':'n','predicate':role,'object_id':pin}
        for j,(role,pin) in enumerate([('loads','a'),('loads','b'),('loads','port'),('driven_by','z')])]
    store=DataStore(tmp_path/'d.sqlite')
    try:
        store.register(pack)
        options={'kind':'instance','connected_to':'signal','net_role':'load'}
        result=list_objects(store,'s',options)
        assert result['count']==1 and result['objects'][0]['name']=='u'
        assert object_statistics(store,'s',{**options,'group_by':'kind'})['object_count']==1
        drivers=list_objects(store,'s',{**options,'net_role':'driver'})
        assert drivers['count']==1 and drivers['objects'][0]['name']=='clock_buf'
        all_related=list_objects(store,'s',{'kind':'instance','connected_to':'signal'})
        assert all_related['count']==2
        inputs=list_objects(store,'s',{'kind':'pin','direction':'INPUT'})
        assert {p['name'] for p in inputs['objects']}=={'u/A','u/B'}
    finally:
        store.close()

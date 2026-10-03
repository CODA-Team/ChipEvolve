"""Pin types remain independent of net classification and pin pagination."""
import base64
import pytest
from openroad_app_data_foundation import pin_inventory as module
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


def row(identifier,name,pin_type,direction,net,net_type):
    encode=lambda s:base64.b64encode(s.encode()).decode()
    return '\t'.join(['EDA_PIN',str(identifier),encode(name),pin_type,direction,encode(net),net_type])


def test_clock_pin_on_signal_net_and_complete_distinct_counts(tmp_path,monkeypatch):
    pack=sample();pack['entities'][0]['attributes']['native_id']='17'
    text='EDA_PIN_TOTAL 4\n'+'\n'.join([
        row(1,'CLK','CLOCK','INPUT','clock_net','SIGNAL'),
        row(2,'A','SIGNAL','INPUT','common','SIGNAL'),
        row(3,'B','SIGNAL','INPUT','common','SIGNAL'),
        row(4,'NC','SIGNAL','INPUT','','')])+'\n'
    def native(store,client,sid,payload,root):
        assert 'dbInst_getInst $b 17' in payload['script'] and not payload['with_timing']
        return {'status':'succeeded','run':{'run_id':'native'},'excerpt':{'text':text,'truncated':False},'source':{'artifact_id':'report'}}
    monkeypatch.setattr(module,'submit_native_query',native)
    store=DataStore(tmp_path/'s.sqlite')
    try:
        store.register(pack)
        result=module.pin_inventory(store,None,'s','u',{'limit':'1','pin_type':'SIGNAL'},tmp_path)
        assert result['total_pin_count']==4
        assert result['pin_counts_by_native_type']=={'SIGNAL':3,'CLOCK':1}
        assert result['connected_pin_counts_by_native_type']=={'SIGNAL':2,'CLOCK':1}
        assert result['distinct_net_counts_by_native_pin_type']=={'SIGNAL':1,'CLOCK':1}
        assert result['count']==3 and result['returned']==1 and result['truncated']
        parsed=module._parse(text)
        clock=next(p for p in parsed if p['local_name']=='CLK')
        assert clock['native_pin_signal_type']=='CLOCK' and clock['connected_net_signal_type']=='SIGNAL'
    finally:store.close()


def test_incomplete_or_duplicated_native_pins_are_reported():
    one=row(1,'A','SIGNAL','INPUT','n','SIGNAL')
    with pytest.raises(ValueError,match='incomplete'):
        module._parse('EDA_PIN_TOTAL 2\n'+one+'\n')
    with pytest.raises(ValueError,match='duplicate'):
        module._parse('EDA_PIN_TOTAL 2\n'+one+'\n'+one+'\n')


def test_indexed_native_pin_summary_keeps_clock_pins_shared_nets_and_missing_classification(tmp_path):
    from openroad_app_data_foundation.engineering import instance_engineering
    pack = sample()
    pack['entities'].append({'object_id': 'clock-net', 'kind': 'net', 'name': 'clock_net',
                             'attributes': {'signal_type': 'SIGNAL'}})
    pack['relations'] = []
    for name, pin_type, net in [('CLK', 'CLOCK', 'clock-net'), ('A', 'SIGNAL', 'n'),
                                ('B', 'SIGNAL', 'n'), ('NC', 'SIGNAL', None)]:
        pack['entities'].append({'object_id': name, 'kind': 'pin', 'name': 'u/' + name,
            'parent_id': 'i', 'attributes': {'native_pin_signal_type': pin_type}})
        if net:
            pack['relations'].append({'relation_id': name + '-net', 'subject_id': name,
                                     'predicate': 'connected_to', 'object_id': net})
    store = DataStore(tmp_path / 'indexed.sqlite')
    try:
        store.register(pack)
        result = instance_engineering(store, 's', 'u')
        assert result['instance']['distinct_signal_net_count'] == 2
        native = result['native_pin_classification']
        assert native['pin_counts_by_native_type'] == {'CLOCK': 1, 'SIGNAL': 3}
        assert native['connected_pin_counts_by_native_type'] == {'CLOCK': 1, 'SIGNAL': 2}
        assert native['distinct_net_counts_by_native_pin_type'] == {'CLOCK': 1, 'SIGNAL': 1}
        assert native['native_pin_classification_coverage']['status'] == 'complete'
        pack['snapshot']['snapshot_id'] = 'missing'
        for row in pack['entities']:
            if row['object_id'] == 'A':
                del row['attributes']['native_pin_signal_type']
        store.register(pack)
        partial = instance_engineering(store, 'missing', 'u')['native_pin_classification']
        assert partial['native_pin_classification_coverage']['status'] == 'partial'
        assert partial['native_pin_classification_coverage']['unclassified_pin_count'] == 1
        assert partial['connected_pin_counts_by_native_type']['SIGNAL'] == 1
    finally:
        store.close()

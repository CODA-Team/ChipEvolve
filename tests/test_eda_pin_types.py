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

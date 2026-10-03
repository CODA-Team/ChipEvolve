"""Rank complete native congestion grids without losing floats or layer ties."""
import pytest
from openroad_app_data_foundation.congestion import _rank


@pytest.mark.parametrize('stage', ['input', 'placeopt', 'global_route'])
def test_implicit_report_is_unique_current_stage_and_same_facts_as_explicit(tmp_path,monkeypatch,stage):
    from openroad_app_data_foundation import congestion as module
    path=tmp_path/(stage+'.congestion.tsv')
    path.write_text('M2\t0\t0\t0\t0\t10\t12\t2\n')
    sid='original-'+stage
    snapshot={'snapshot_id':sid,'design_id':'design','revision_id':'revision','run_id':'run','stage':stage,
              'run_summary':{'dbu_per_micron':1000,'die_bbox':{'x_max':10000,'y_max':10000}}}
    class Store:
        def snapshot(self,identifier):
            assert identifier==sid
            return snapshot
    calls=[]
    def catalog(store,identifier,query,root):
        calls.append(query)
        assert identifier==sid and query['kind']=='reports' and query['name_contains']==stage+'.congestion.tsv'
        return {'files':{'count':1,'items':[{'relative_path':'reports/'+path.name}]}}
    def excerpt(store,identifier,query,root):
        assert query['path']=='reports/'+path.name
        return {'source':{'path':str(path),'sha256':'a'*64}}
    monkeypatch.setattr(module,'native_files',catalog)
    monkeypatch.setattr(module,'native_excerpt',excerpt)
    implicit=module.congestion_grid(Store(),sid,{'layers':'M2','limit':'1'},tmp_path)
    explicit=module.congestion_grid(Store(),sid,{'layers':'M2','limit':'1','file':'reports/'+path.name},tmp_path)
    assert implicit==explicit and len(calls)==1
    assert implicit['count']==1 and implicit['total_overflow']==2
    assert implicit['cells'][0]['bbox_um']==[0,0,10,10]


@pytest.mark.parametrize('catalog',[
    {'count':0,'items':[]},
    {'count':2,'items':[{'relative_path':'reports/global_route.congestion.tsv'}]},
    {'count':1,'items':[{'relative_path':'reports/old_global_route.congestion.tsv'}]},
])
def test_absent_ambiguous_or_another_stage_never_returns_an_invented_grid(tmp_path,monkeypatch,catalog):
    from openroad_app_data_foundation import congestion as module
    class Store:
        def snapshot(self,identifier):return {'stage':'global_route'}
    monkeypatch.setattr(module,'native_files',lambda *a: {'files':catalog})
    monkeypatch.setattr(module,'native_excerpt',lambda *a: pytest.fail('ambiguous report must not be read'))
    with pytest.raises(ValueError,match='no unique report for snapshot stage global_route'):
        module.congestion_grid(Store(),'s',{},tmp_path)


def test_public_physical_help_lists_actual_grid_fields():
    from openroad_app_data_foundation import api_help
    text=api_help.QUICK_GUIDES['physical']
    assert 'fields=cells,count,overflow_cell_count,total_overflow,source' in text
    assert 'cells/counts/sources' not in text


def test_float_capacity_full_domain_ranking_and_layer_filter(tmp_path):
    path=tmp_path/'grid.tsv'
    path.write_text('M1\t0\t0\t0\t0\t0.0\t100.0\t100\n'
                    'M10\t0\t0\t0\t0\t10.5\t12.5\t2\n'
                    'M2\t1\t0\t10\t0\t10.5\t12.5\t2\n'
                    'M2\t0\t0\t0\t0\t10.5\t12.5\t2\n'
                    'M2\t0\t1\t0\t20\t20.0\t21.0\t1\n')
    st=path.stat()
    ranked,xs,ys,count,over,total,layers=_rank(str(path),st.st_size,st.st_mtime_ns,('M2','M10'),2)
    assert count==4 and over==4 and total==7
    assert layers=={'M10':1,'M2':3}
    assert [item[2][:3] for item in ranked]==[('M2',0,0),('M2',1,0)]
    assert ranked[0][2][5:8]==(10.5,12.5,2.0)
    assert xs==[0,10] and ys==[0,20]


def test_zero_capacity_tie_and_invalid_report_are_explicit(tmp_path):
    path=tmp_path/'grid.tsv'
    path.write_text('M2\t0\t0\t0\t0\t0.0\t1.0\t1\nM2\t1\t0\t1\t0\t1\t2\t1\n')
    st=path.stat()
    ranked,*_= _rank(str(path),st.st_size,st.st_mtime_ns,(),1)
    assert ranked[0][2][1]==1
    path.write_text('M2\t0\t0\t0\t0\t1\t3\t1\n')
    st=path.stat()
    with pytest.raises(ValueError,match='quantities'):
        _rank(str(path),st.st_size,st.st_mtime_ns,(),1)

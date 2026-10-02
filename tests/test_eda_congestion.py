"""Rank complete native congestion grids without losing floats or layer ties."""
import pytest
from openroad_app_data_foundation.congestion import _rank


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

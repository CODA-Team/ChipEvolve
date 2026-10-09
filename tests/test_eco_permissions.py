"""Unauthorized cell edits and evaluation changes are rejected before execution."""
from copy import deepcopy
import pytest
from eda_toolkits.eco import buffer_eco_task


def fixture():
    refs = [{'category':kind,'logical_path':path,'artifact_id':'art-'+kind,
             'sha256':'a'*64,'run_id':'run','size_bytes':10}
            for kind,path in [('raw_design_database','design.odb'),
                              ('raw_constraints','design.sdc'),('raw_library','cells.lib')]]
    snapshot = {'snapshot_id':'s','design_id':'gcd','revision_id':'r','run_id':'run','stage':'finish',
                'source_artifacts':refs,
                'run_summary':{'timing_context':{'executor':'openroad','constraints':'design.sdc',
                                                'libraries':['cells.lib'],'parasitic_mode':'placement',
                                                'rc_script':'rc.tcl'}}}
    refs.append({'category':'analysis_script','logical_path':'rc.tcl','artifact_id':'art-rc',
                 'sha256':'b'*64,'run_id':'run','size_bytes':10})
    package = {'role':'eco','consumer_status':'ready','scope':{k:snapshot[k] for k in
                ('snapshot_id','design_id','revision_id','run_id','stage')},
               'fixed_inputs':refs,'handoff_id':'handoff-test','investigation_id':'inv-test',
               'budget':{'max_experiments':1,'max_seconds':180,'cpu_cores':2,'memory_bytes':6*1024**3},
               'buffer_permissions':[{'instance':'place178','original_master':'BUF_X1','allowed_masters':['BUF_X4']}]}
    proposal={'changes':[{'instance':'place178','target_master':'BUF_X4'}],'reason':'bounded sizing experiment'}
    return snapshot,package,proposal


def test_allowed_buffer_task_keeps_original_sources_and_native_checks():
    snapshot,package,proposal=fixture()
    task=buffer_eco_task(snapshot,package,proposal)
    assert task['inputs']['sdc_path']=='design.sdc'
    assert task['inputs']['rc_script_path']=='rc.tcl'
    assert task['inputs']['liberty_paths']==['cells.lib']
    assert 'outputs/setup.json' in task['inputs']['native_extra_paths']
    assert 'outputs/hold.json' in task['inputs']['native_extra_paths']


@pytest.mark.parametrize('change',[
    {'instance':'unpermitted','target_master':'BUF_X4'},
    {'instance':'place178','target_master':'BUF_X8'},
    {'instance':'place178','target_master':'BUF_X4','clock_period':0.3},
])
def test_unapproved_edits_cannot_create_an_execution_task(change):
    snapshot,package,proposal=fixture()
    proposal['changes']=[change]
    with pytest.raises(ValueError):buffer_eco_task(snapshot,package,proposal)


def test_changed_input_hash_or_unconnected_role_is_rejected():
    snapshot,package,proposal=fixture()
    package['fixed_inputs']=deepcopy(package['fixed_inputs'])
    package['fixed_inputs'][1]['sha256']='c'*64
    with pytest.raises(ValueError,match='identity'):buffer_eco_task(snapshot,package,proposal)
    package['role']='flow'
    with pytest.raises(ValueError,match='only the ECO'):buffer_eco_task(snapshot,package,proposal)

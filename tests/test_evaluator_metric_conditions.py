"""Fixed-clock evaluator facts retain their producer and comparison conditions."""
from openroad_app_data_foundation.metrics import project_run
from openroad_app_data_foundation.repository import DataStore


def test_evaluator_conditions_survive_metric_projection_and_database_restart(tmp_path):
    conditions = {'cp0_ns': .792, 'clock_port': 'clk', 'parasitic_mode': 'spef',
                  'library_patterns': ['/frozen/NangateOpenCellLibrary_typical.lib'],
                  'profile_sha256': 'a' * 64}
    evidence = [{'artifact_id': 'measured', 'logical_path': 'a2-evaluation.json'}]
    values = {'timing__setup__tns': -4.36, 'timing__setup__wns': -.08,
              'power__total': .4, 'flow__platform__time_units': '1ns'}
    pack = {'snapshot': {'snapshot_id': 'eval', 'design_id': 'aes', 'revision_id': 'revision',
                         'run_id': 'physical', 'stage': 'eval_final', 'created_at': '2026-10-10',
                         'source_artifacts': [{'artifact_id': 'measured', 'run_id': 'analysis',
                                               'logical_path': 'a2-evaluation.json',
                                               'category': 'raw_flow_metadata',
                                               'stage': 'eval_final',
                                               'sha256': 'b' * 64, 'size_bytes': 42}]},
            'observations': [{'observation_id': 'metric:eval_final__' + key,
                              'kind': 'metric', 'value': value, 'evidence': evidence,
                              'context': {'authoritative_source': 'a2_cp0_evaluator',
                                          'evaluation_conditions': conditions}}
                             for key, value in values.items()]}
    store = DataStore(tmp_path / 'facts.sqlite')
    store.register(pack)
    store.close()
    store = DataStore(tmp_path / 'facts.sqlite')
    try:
        metrics = project_run(store, [store.snapshot('eval')])['metrics']
        rows = {row['name']: row for row in metrics if row['status'] == 'available'}
        # report_wns does not report positive worst slack; do not invent a WS fact.
        assert set(rows) == {'WNS', 'TNS', 'POWER_TOTAL'}
        assert rows['TNS']['value'] == -4.36 and rows['TNS']['unit'] == 'ns'
        assert rows['WNS']['value'] == -.08 and rows['WNS']['unit'] == 'ns'
        assert rows['POWER_TOTAL']['value'] == .4 and rows['POWER_TOTAL']['unit'] == 'W'
        for row in rows.values():
            assert row['authoritative_source'] == 'a2_cp0_evaluator'
            assert row['evaluation_conditions'] == conditions
            source = row['evidence'][0]
            assert source['artifact_id'] == 'measured'
            assert source['logical_path'] == 'a2-evaluation.json'
            assert source['sha256'] == 'b' * 64
            assert source['resolution'] == 'exact_artifact'
    finally:
        store.close()

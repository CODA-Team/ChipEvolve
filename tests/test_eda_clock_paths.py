"""Native clock report nulls/order must survive independently of mapped ODB facts."""
from openroad_app_data_foundation.clock_paths import clock_paths


def test_clock_join_reads_original_nulls_and_complete_clock_arrays():
    from tests.test_eda_engineering import sample
    import json
    report = {'source_clock': 'clk', 'source_clock_latency': .2,
        'source_path': [{'pin': 'data/A'}],
        'source_clock_path': [{'pin': 'clk', 'instance': None, 'net': None}, {'pin': 'buf/Z', 'instance': 'buf', 'net': 'clock_net'}],
        'target_clock_path': [{'pin': 'clk', 'instance': None, 'net': None}]}
    class Store:
        def records(self, *args, **kwargs):
            return [{'path_id': 'p', 'evidence': [{'logical_path': 'original.json', 'detail': {'path_index': 0}}]}]
        def fragment_source(self, *args):
            return {'payload': json.dumps({'checks': [report]}).encode()}
        def snapshot(self, *args):
            return sample()['snapshot']
    result = clock_paths(Store(), 's', 'p')
    assert result['source_clock_path'] == report['source_clock_path']
    assert result['target_clock_path'] == report['target_clock_path']
    assert result['report_header']['source_clock_latency'] == .2
    assert 'source_path' not in result['report_header']
    assert result['clock_point_counts'] == {'source_clock_path': 2, 'target_clock_path': 1}
    assert result['source_clock_path'][0]['instance'] is None

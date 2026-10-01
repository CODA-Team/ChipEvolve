"""Native scenes/units must not be substituted with configured snapshot labels."""
import pytest

from openroad_app_data_foundation.analysis_setup import analysis_setup


def test_actual_default_scene_and_empty_named_corner_list_are_both_preserved(monkeypatch):
    class Store:
        def snapshot(self, sid):
            return {'snapshot_id': sid, 'run_summary': {'timing_context': {'corner': 'typical'}}}
    text = ('EDA_SETUP_UNITS_BEGIN\n time 1ns\n capacitance 1fF\n resistance 1kohm\n'
            ' voltage 1v\n current 1mA\n power 1nW\n distance 1um\nEDA_SETUP_UNITS_END\n'
            'EDA_SETUP_SCENE default\nEDA_SETUP_LIBRARY actual_lib\n'
            'EDA_SETUP_COMMAND_CORNER NULL\nEDA_SETUP_COMPLETE\n')
    def native(store, client, sid, query, root):
        assert query['with_timing'] is True
        return {'run': {'run_id': 'actual-query'}, 'status': 'succeeded', 'source': {'artifact_id': 'source'},
                'excerpt': {'text': text}, 'original_input_artifacts': [{'artifact_id': 'actual-input'}]}
    monkeypatch.setattr('openroad_app_data_foundation.analysis_setup.submit_native_query', native)
    result = analysis_setup(Store(), None, 's', None)
    assert result['scene_names'] == ['default']
    assert result['explicit_analysis_corner_names'] == []
    assert result['snapshot_analysis_labels']['corner'] == 'typical'
    assert result['native_ui_units']['time'] == '1ns'
    assert result['loaded_liberty_names'] == ['actual_lib']
    assert result['original_input_artifacts'] == [{'artifact_id': 'actual-input'}]


def test_incomplete_setup_report_never_invents_empty_scenes(monkeypatch):
    class Store:
        def snapshot(self, sid): return {'snapshot_id': sid}
    monkeypatch.setattr('openroad_app_data_foundation.analysis_setup.submit_native_query',
        lambda *args: {'run': {'run_id': 'r'}, 'status': 'succeeded', 'excerpt': {'text': 'time 1ns'}})
    with pytest.raises(ValueError, match='incomplete or malformed'):
        analysis_setup(Store(), None, 's', None)

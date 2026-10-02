"""Native supplement retains the exact global-routing file of its snapshot."""
from openroad_app_data_foundation.analysis_context import build_analysis_context, context_availability
from openroad_app_data_foundation.query_inputs import snapshot_inputs


def test_global_route_snapshot_preserves_native_reconstruction_inputs():
    context = {'executor': '/tools/openroad', 'constraints': 'inputs/clock.sdc',
               'libraries': ['inputs/standard.lib', 'inputs/memory.lib'],
               'rc_script': 'inputs/rc.tcl', 'parasitics': None,
               'global_routing_segments': 'inputs/route.segments',
               'parasitic_mode': 'global_routing', 'ideal_clocks': True}
    snapshot = {'run_summary': {'timing_context': context}, 'source_artifacts': [
        {'category': 'raw_design_database', 'logical_path': 'inputs/design.odb', 'artifact_id': 'db'},
        {'category': 'raw_constraints', 'logical_path': 'inputs/clock.sdc', 'artifact_id': 'sdc'},
        {'category': 'raw_library', 'logical_path': 'inputs/standard.lib', 'artifact_id': 'cells'},
        {'category': 'raw_library', 'logical_path': 'inputs/memory.lib', 'artifact_id': 'macros'},
        {'category': 'analysis_script', 'logical_path': 'inputs/rc.tcl', 'artifact_id': 'rc'},
        {'category': 'raw_layout', 'logical_path': 'inputs/route.segments', 'artifact_id': 'routes'}]}
    inputs, staged = snapshot_inputs(snapshot)
    assert inputs['global_routing_segments_path'] == 'inputs/route.segments'
    assert inputs['parasitic_mode'] == 'global_routing'
    assert inputs['ideal_clocks'] is True
    assert {'destination': 'inputs/route.segments', 'artifact_id': 'routes'} in staged
    analysis = build_analysis_context(snapshot)
    availability = context_availability(analysis)
    assert availability['parasitic'] == {'status': 'available', 'mode': 'global_routing',
                                        'source': 'inputs/route.segments'}

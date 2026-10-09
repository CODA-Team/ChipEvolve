"""Report-driven mapping preserves all clock/data occurrences and exact names."""
import base64
import json
import subprocess
import sys




def test_mapping_domain_is_all_actual_sections_of_both_reports(tmp_path):
    setup = {'checks': [{'source_clock_path': [{'pin': 'clk'}],
                         'source_path': [{'pin': 'u/q[3]'}, {'pin': 'u/q[3]'}],
                         'target_clock_path': [{'pin': 'capture/Z'}],
                         'target_path': [{'pin': 'capture/D'}]}]}
    hold = {'checks': [{'points': [{'pin_name': 'hold/$pin\\[0]'}, {'pin': '单元/A'}]}]}
    (tmp_path / 'timing_report.json').write_text(json.dumps(setup))
    (tmp_path / 'timing_report_hold.json').write_text(json.dumps(hold))
    result = subprocess.run([sys.executable, "-m", "eda_toolkits.openroad.timing_json", str(tmp_path)], check=True,
                            capture_output=True, text=True)
    names = [base64.b64decode(value).decode() for value in result.stdout.split()]
    assert names == sorted(['clk', 'u/q[3]', 'capture/Z', 'capture/D', 'hold/$pin\\[0]', '单元/A'])
    # Normalization consumes the same parser and retains repeated occurrences.
    result = subprocess.run([sys.executable, '-c',
        'import json; from eda_toolkits.openroad.opensta_adapter import _points; print(json.dumps(_points(json.loads(input()))))'],
        input=json.dumps(setup['checks'][0]), capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout)
    assert [row['pin'] for row in rows] == ['clk', 'u/q[3]', 'u/q[3]', 'capture/Z', 'capture/D']
    assert [row['path_section'] for row in rows] == ['source_clock_path', 'source_path', 'source_path',
                                                  'target_clock_path', 'target_path']


def test_empty_native_reports_have_an_empty_mapping_domain(tmp_path):
    for filename in ('timing_report.json', 'timing_report_hold.json'):
        (tmp_path / filename).write_text('{"checks": []}')
    result = subprocess.run([sys.executable, "-m", "eda_toolkits.openroad.timing_json", str(tmp_path)], check=True,
                            capture_output=True, text=True)
    assert result.stdout.strip() == ''


def test_valid_empty_reports_keep_analysis_identity_and_requested_domain(tmp_path):
    from eda_toolkits.openroad.opensta_adapter import normalize

    (tmp_path/'timing_report.json').write_text('{"checks":[]}')
    (tmp_path/'timing_report_hold.json').write_text('{"checks":[]}')
    inputs={'snapshot_id':'empty','design_id':'gcd','revision_id':'r','run_id':'run',
            'created_at':'2026-10-08T00:00:00Z','stage':'finish',
            'liberty_paths':['library.lib'],'sdc_path':'original.sdc','spef_path':'original.spef',
            'openroad_bin':'eda-openroad','to_pin':'clk','corner':'typical','analysis':'default'}
    normalize(tmp_path,inputs)
    summary=json.loads((tmp_path/'summary.json').read_text())
    assert summary['timing_path_count']==0
    assert summary['timing_context']['constraints']=='original.sdc'
    assert summary['timing_context']['requested_filters']=={'to_pin':'clk'}
    assert json.loads((tmp_path/'coverage.json').read_text())['timing']=='empty'
    assert (tmp_path/'timing_paths.jsonl').read_text()==''

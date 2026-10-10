"""Stage inheritance and fixed-clock feedback at the native execution boundary."""
import hashlib
import json
import stat
import zipfile

import pytest

from eda_toolkits.openroad.a2_checkpoint import restore_checkpoint
from eda_toolkits.openroad.a2_evaluation import parse_evaluation
from eda_toolkits.openroad.a2_stage import run_stage


def test_restored_predecessors_do_not_rebuild_missing_upstream(tmp_path):
    source = tmp_path / 'native'
    source.mkdir()
    makefile = source / 'Makefile'
    makefile.write_text('''cts: $(RESULTS_DIR)/4_cts.odb $(RESULTS_DIR)/4_cts.sdc
$(RESULTS_DIR)/4_cts.odb: $(RESULTS_DIR)/3_place.odb $(RESULTS_DIR)/3_place.sdc
\tcp $(RESULTS_DIR)/3_place.odb $@
$(RESULTS_DIR)/4_cts.sdc: $(RESULTS_DIR)/4_cts.odb
\tcp $(RESULTS_DIR)/3_place.sdc $@
$(RESULTS_DIR)/3_place.odb: $(RESULTS_DIR)/missing_synth.v
\t$(error upstream must not be rebuilt)
$(RESULTS_DIR)/3_place.sdc: $(RESULTS_DIR)/missing_floorplan.sdc
\t$(error upstream SDC must not be rebuilt)
''')
    profile = {'flow_dir': str(source), 'makefile_sha256': hashlib.sha256(makefile.read_bytes()).hexdigest(),
               'source_commit': 'a' * 40, 'openroad_bin': '/usr/bin/true',
               'yosys_bin': '/usr/bin/true', 'python_bin': '/usr/bin/python3'}
    workspace = tmp_path / 'attempt'
    workspace.mkdir()
    (workspace / 'profile.json').write_text(json.dumps(profile))
    original_config = b'export CTS_CLUSTER_SIZE = 24\n'
    (workspace / 'candidate.mk').write_bytes(original_config)
    (workspace / 'candidate.sdc').write_text('create_clock -period 1 clk\n')
    with zipfile.ZipFile(workspace / 'checkpoint.zip', 'w') as archive:
        archive.writestr('flow/results/3_place.odb', b'predecessor-bytes')
        archive.writestr('flow/results/3_place.sdc', b'predecessor-clock')
        archive.writestr('flow/results/4_cts.odb', b'stale-downstream-must-be-removed')
        archive.writestr('flow/objects/copyright.txt', b'native-license')
        archive.writestr('flow/combined.log', 'inherited-placement-history\n')
    result = workspace / 'result.json'
    assert run_stage(result, '2026-10-10T00:00:00Z', workspace, {
        'stage': 'cts', 'threads': 2, 'profile_path': 'profile.json',
        'config_path': 'candidate.mk', 'sdc_path': 'candidate.sdc',
        'checkpoint_path': 'checkpoint.zip'}) == 0
    payload = json.loads(result.read_text())
    assert payload['status'] == 'succeeded'
    assert (workspace / 'flow/results/4_cts.odb').read_bytes() == b'predecessor-bytes'
    assert (workspace / 'candidate.mk').read_bytes() == original_config
    with zipfile.ZipFile(workspace / 'flow-artifacts.zip') as archive:
        assert archive.read('flow/objects/copyright.txt') == b'native-license'
        assert archive.read('flow/combined.log').startswith(b'inherited-placement-history\n')
    receipt = json.loads((workspace / 'extractor_receipt.json').read_text())
    assert receipt['config_sha256'] == hashlib.sha256(original_config).hexdigest()


@pytest.mark.parametrize('member', ['../outside', '/absolute', 'flow/../../outside',
                                   'flow/inputs/overwrite', 'combined.log/child'])
def test_checkpoint_cannot_overwrite_staged_inputs_or_escape_attempt(tmp_path, member):
    archive = tmp_path / 'checkpoint.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(member, b'invalid')
    with pytest.raises(ValueError):
        restore_checkpoint(archive, tmp_path / 'flow')
    assert not (tmp_path / 'outside').exists()


def test_checkpoint_rejects_links(tmp_path):
    archive = tmp_path / 'checkpoint.zip'
    entry = zipfile.ZipInfo('flow/results/3_place.odb')
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(entry, '../../input')
    with pytest.raises(ValueError, match='link'):
        restore_checkpoint(archive, tmp_path / 'flow')


def test_cp0_feedback_reads_native_report_and_ignores_debug_labels():
    content = '''DEBUG: --- report_tns ---
tns max -4.36
wns max -0.08
DEBUG: --- report_power under CP_0 = 0.7920 ---
Total                  1.90e-01   2.10e-01   5.32e-04   4.00e-01 100.0%
'''
    assert parse_evaluation(content) == {'tns': {'value': -4.36, 'unit': 'ns'},
                                          'wns': {'value': -.08, 'unit': 'ns'},
                                          'power': {'value': .4, 'unit': 'W'}}


@pytest.mark.parametrize('content', ['tns max -4.36\nwns max -.08\n',
                                    'tns max -4.36\nwns max -.08\nTotal 1 2 3 nan\n',
                                    'tns max -4.36\nwns max -.08\nTotal 1 2 3 -1\n'])
def test_cp0_feedback_without_valid_power_is_not_successful(content):
    with pytest.raises(ValueError):
        parse_evaluation(content)


@pytest.mark.parametrize('power_report', ['Total 1.90e-1 2.10e-1 5.32e-4 4.00e-1 100%\n', ''])
def test_native_evaluation_preserves_fixed_context_and_rejects_incomplete_success(tmp_path, monkeypatch, power_report):
    script = tmp_path / 'eval_tns.tcl'
    script.write_text('# frozen native evaluator\n')
    profile = {'flow_dir': str(tmp_path), 'eval_tns_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
               'source_commit': 'a' * 40, 'openroad_bin': '/usr/bin/true',
               'yosys_bin': '/usr/bin/true', 'python_bin': '/usr/bin/python3'}
    (tmp_path / 'profile.json').write_text(json.dumps(profile))
    with zipfile.ZipFile(tmp_path / 'checkpoint.zip', 'w') as archive:
        archive.writestr('flow/results/6_final.odb', b'native-predecessor')
        archive.writestr('flow/results/6_final.spef', b'native-parasitics')
    captured = {}

    def native_report(command, workspace, *, environment):
        captured.update(command=command, environment=environment)
        (workspace / 'extractor.log').write_text('tns max -4.36\nwns max -0.08\n' + power_report)
        return 0

    monkeypatch.setattr('eda_toolkits.openroad.a2_stage.run_logged', native_report)
    result = tmp_path / 'result.json'
    returncode = run_stage(result, '2026-10-10T00:00:00Z', tmp_path, {
        'stage': 'eval_final', 'threads': 2, 'profile_path': 'profile.json',
        'checkpoint_path': 'checkpoint.zip', 'evaluation': {
            'cp0_ns': .792, 'clock_port': 'clk', 'library_patterns': ['/frozen/platform/*.lib']}})
    assert captured['environment']['CP0'] == '0.792'
    assert captured['environment']['LIB_FILES'] == '/frozen/platform/*.lib'
    assert captured['environment']['SPEF_PATH'] == str(tmp_path / 'flow/results/6_final.spef')
    assert captured['command'][-1] == str(script)
    payload = json.loads(result.read_text())
    assert returncode == (0 if power_report else 1)
    assert payload['status'] == ('succeeded' if power_report else 'failed')
    receipt = json.loads((tmp_path / 'extractor_receipt.json').read_text())
    assert receipt['parasitic_mode'] == 'spef'
    if not power_report:
        assert payload['failure']['category'] == 'a2_evaluation_missing'
        assert 'flow_archive' in {artifact['kind'] for artifact in payload['artifacts']}
        assert not (tmp_path / 'a2-evaluation.json').exists()
    else:
        feedback = json.loads((tmp_path / 'a2-evaluation.json').read_text())
        assert feedback['evaluation']['cp0_ns'] == .792
        assert feedback['parasitic_mode'] == 'spef'
        assert feedback['metrics'] == {
            'eval_final__timing__setup__tns': -4.36,
            'eval_final__timing__setup__wns': -.08,
            'eval_final__power__total': .4,
            'eval_final__flow__platform__time_units': '1ns'}
        assert feedback['source_log']['sha256'] == hashlib.sha256(
            (tmp_path / 'extractor.log').read_bytes()).hexdigest()
        assert {'kind': 'raw_flow_metadata', 'path': 'a2-evaluation.json'} in payload['artifacts']

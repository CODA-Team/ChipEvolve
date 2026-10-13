"""Invoke the frozen A2 CP0 evaluator and retain its real observations."""
import math
import re


def time_to_ns(unit):
    """The A2 controller keeps native units; public observations use ns."""
    if unit not in {'ns', 'ps'}:
        raise ValueError('A2 source_time_unit must be ns or ps')
    return {'ns': 1.0, 'ps': 0.001}[unit]


def evaluation_plan(inputs, profile, flow, environment):
    stage = inputs['stage']
    stem = {'eval_place': '3_place', 'eval_cts': '4_cts', 'eval_final': '6_final'}[stage]
    evaluation = inputs['evaluation']
    cp0 = float(evaluation['cp0_ns'])
    if not math.isfinite(cp0) or cp0 <= 0:
        raise ValueError('cp0_ns must be a finite positive reference clock')
    patterns = evaluation['library_patterns']
    if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) and p for p in patterns):
        raise ValueError('library_patterns must contain the frozen native library patterns')
    native_cp0 = cp0 / time_to_ns(evaluation.get('source_time_unit', 'ns'))
    environment.update(CP0=str(native_cp0), CLK_PORT=evaluation['clock_port'],
                       LIB_FILES=' '.join(patterns), ODB_PATH=str(flow / 'results' / f'{stem}.odb'),
                       SPEF_PATH=str(flow / 'results' / f'{stem}.spef'))
    return [profile['openroad_bin'], '-no_init', '-threads', str(inputs['threads']),
            '-exit', profile['flow_dir'] + '/eval_tns.tcl']


def parse_evaluation(content, *, source_time_unit='ns'):
    observations = {}
    for name, unit in (('tns', 'ns'), ('wns', 'ns')):
        matches = re.findall(r'^\s*' + name + r'(?:\s+max)?\s+([-+\d.eE]+)\s*$', content, re.M)
        if not matches:
            raise ValueError('native CP0 evaluator did not report ' + name)
        value = float(matches[-1])
        if not math.isfinite(value):
            raise ValueError('native CP0 evaluator reported non-finite ' + name)
        observations[name] = {'value': value * time_to_ns(source_time_unit), 'unit': unit}
    rows = re.findall(r'^Total\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', content, re.M)
    if not rows or not math.isfinite(power := float(rows[-1][3])) or power < 0:
        raise ValueError('native CP0 evaluator did not report finite non-negative total power')
    observations['power'] = {'value': power, 'unit': 'W'}
    return observations

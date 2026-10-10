"""Portable metric facts from the actual fixed-clock evaluator receipt."""
import hashlib
import json


def write_feedback(workspace, receipt):
    stage = receipt['stage']
    observations = receipt['observations']
    payload = {
        'metrics': {
            stage + '__timing__setup__tns': observations['tns']['value'],
            stage + '__timing__setup__wns': observations['wns']['value'],
            stage + '__power__total': observations['power']['value'],
            stage + '__flow__platform__time_units': '1ns',
        },
        'evaluation': receipt['evaluation'],
        'parasitic_mode': receipt['parasitic_mode'],
        'profile': receipt['profile'],
        'profile_sha256': receipt['profile_sha256'],
        'source_log': {'path': 'extractor.log', 'sha256': hashlib.sha256(
            (workspace / 'extractor.log').read_bytes()).hexdigest()},
        'observations': observations,
        'metric_context': {
            'authoritative_source': 'a2_cp0_evaluator',
            'evaluation_conditions': {
                **receipt['evaluation'], 'parasitic_mode': receipt['parasitic_mode'],
                'profile_sha256': receipt['profile_sha256'],
            },
        },
    }
    (workspace / 'a2-evaluation.json').write_text(json.dumps(payload, indent=2) + '\n')
    return {'kind': 'raw_flow_metadata', 'path': 'a2-evaluation.json'}

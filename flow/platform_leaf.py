"""Translate one native A2 leaf invocation, including real clone ancestry."""
import argparse
import json
import os
import shlex
from pathlib import Path

from lineage import config_snapshot
from openroad_platform_client import KernelClient
from platform_execution import PlatformExecution
from platform_feedback import publish_feedback


def candidate_binding(flow, campaign, iteration, slot, stage):
    lifecycle = json.loads((flow / f'tmp/candidate_lifecycle_iter{iteration}.json').read_text())
    if lifecycle['campaign_id'] != campaign or lifecycle['iteration'] != iteration:
        raise ValueError('Native candidate lifecycle does not match the active campaign.')
    candidate = next(row for row in lifecycle['slots'] if row['run_id'] == slot)
    donor = slot
    if stage in {'cts', 'route_finish'}:
        lineage = json.loads((flow / f'tmp/lineage_iter{iteration}.json').read_text())
        if lineage['campaign_id'] != campaign or lineage['iteration'] != iteration:
            raise ValueError('Native checkpoint lineage does not match the active campaign.')
        previous = 'place' if stage == 'cts' else 'cts'
        for event in lineage['stages'][previous]:
            if event['target_run_id'] == slot:
                if not event['trusted']:
                    raise ValueError('Native clone ancestry is not trusted.')
                donor = event['source_run_id']
    return candidate['candidate_id'], donor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('slot', type=int)
    parser.add_argument('platform')
    parser.add_argument('design')
    parser.add_argument('stage', choices=['place', 'cts', 'route_finish',
                                         'eval_place', 'eval_cts', 'eval_final'])
    args = parser.parse_args()
    flow = Path(__file__).resolve().parent
    settings = json.loads(Path(os.environ['DRP_PLATFORM_CONFIG']).read_text())
    iteration = int(os.environ['DRP_ITER'])
    campaign = os.environ['DRP_CAMPAIGN_ID']
    candidate_id, donor = candidate_binding(flow, campaign, iteration, args.slot, args.stage)
    client = KernelClient(settings['kernel_url'], timeout=60)
    executor = PlatformExecution(client, flow, settings['state_root'], settings['profile_path'],
                                 campaign, settings['threads'], settings['timeout_seconds'])
    evaluation = None
    sdc = None
    if args.stage.startswith('eval_'):
        evaluation = {'cp0_ns': float(os.environ['CP0']), 'clock_port': os.environ['CLK_PORT'],
                      'library_patterns': shlex.split(os.environ['LIB_FILES'])}
    else:
        snapshot = config_snapshot(args.config)
        if snapshot['effective_sdc']['resolved_path'] is None:
            raise ValueError('Native candidate has no resolved SDC.')
        sdc = Path(snapshot['effective_sdc']['resolved_path'])
    record = executor.execute(iteration=iteration, slot=args.slot, candidate_id=candidate_id,
                              platform=args.platform, design=args.design, stage=args.stage,
                              config=args.config, sdc=sdc, evaluation=evaluation,
                              donor_slot=None if args.stage == 'place' else donor)
    if evaluation is not None:
        publish_feedback(client, settings['state_root'], settings['data_url'], record)
    print(json.dumps({'stage': args.stage, 'run_id': record['run_id'],
                      'candidate_id': candidate_id, 'status': record['status']}))


if __name__ == '__main__':
    main()

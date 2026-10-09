"""Actual Toolkit -> EF -> DF analysis, followed by a fresh investigation host."""
import argparse
import json
from pathlib import Path
import time

from eda_ai_client import EdaAiClient
from eda_toolkits.inputs import SnapshotExecutionClient

from query_agent.adapters.investigation.analysis import ToolkitAnalysis
from query_agent.adapters.investigation.data import ScopedDataReads
from query_agent.adapters.investigation.skills import InstalledInvestigationSkills
from query_agent.adapters.investigation.store import JsonInvestigationStore
from query_agent.application.investigation import InvestigationService
from query_agent.domain.investigation import AnalysisRequest, InvestigationDecision


def application(args):
    client = EdaAiClient(args.data_url, kernel_url=args.kernel_url)
    reader = ScopedDataReads(client, args.output / 'evidence')
    return InvestigationService(
        data=reader,
        analysis=ToolkitAnalysis(client, SnapshotExecutionClient(args.kernel_url), reader),
        store=JsonInvestigationStore(args.output / 'investigations'),
        skills=InstalledInvestigationSkills(),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-url', default='http://127.0.0.1:18924')
    parser.add_argument('--kernel-url', default='http://127.0.0.1:18700')
    parser.add_argument('--snapshot', default='gcd-sprint30h2-finish')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = application(args)
    state = app.create('Verify setup and hold for resp_msg[12] with fixed original inputs',
                       [args.snapshot])
    decision = InvestigationDecision(
        action='analyze', reasoning_summary='Sampled paths do not establish endpoint hold coverage.',
        analysis=AnalysisRequest(snapshot_id=args.snapshot, to_pin='resp_msg[12]',
                                 question_to_verify='Endpoint setup and hold under original conditions',
                                 path_count=5, endpoint_path_count=1),
    )
    app.apply(state, decision)
    (args.output / 'before-host-restart.json').write_text(state.model_dump_json(indent=2))
    print(state.investigation_id, state.status, flush=True)
    # Recreate all adapters and the store. The receiver knows only the saved ID.
    fresh = application(args)
    restored = fresh.store.load(state.investigation_id)
    initial_scopes = restored.scopes.copy()
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        start = time.monotonic()
        fresh.poll(restored)
        restored.active_seconds += time.monotonic() - start
        fresh.store.save(restored, restored.revision)
        if restored.pending_analyses and all(
            ticket.status in ('imported', 'failed', 'cancelled', 'timed_out', 'lost')
            for ticket in restored.pending_analyses
        ):
            break
        time.sleep(0.25)
    imported = [ticket for ticket in restored.pending_analyses if ticket.status == 'imported']
    passed = len(imported) == 1 and restored.scopes[:len(initial_scopes)] == initial_scopes
    if imported:
        for endpoint in ('summary', 'constraints', 'timing-paths'):
            result = fresh.data.client.read_query('/snapshots/' + imported[0].snapshot_id + '/' + endpoint)
            (args.output / (endpoint + '.json')).write_text(json.dumps(result, indent=2))
        paths = json.loads((args.output / 'timing-paths.json').read_text())['data']['timing_paths']
        passed &= bool(paths) and all(path['endpoint'] == 'resp_msg[12]' for path in paths)
        checks = {path['check'] for path in paths}
        passed &= checks == {'setup', 'hold'}
    result = {'passed': passed, 'investigation_id': restored.investigation_id,
              'pending_analyses': [ticket.model_dump(mode='json') for ticket in restored.pending_analyses],
              'scopes': [scope.model_dump(mode='json') for scope in restored.scopes]}
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

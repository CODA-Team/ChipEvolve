"""A2 leaf tasks use public EF contracts; native A2 still owns every decision."""
import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path

from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec

TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'lost'}
STEMS = {'place': '3_place', 'cts': '4_cts', 'route_finish': '6_final'}
PREDECESSORS = {'cts': 'place', 'route_finish': 'cts',
                'eval_place': 'place', 'eval_cts': 'cts', 'eval_final': 'route_finish'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, path)


def find_predecessor(state, flow, campaign, iteration, platform, design, slot, stage,
                     donor_slot=None):
    previous = PREDECESSORS[stage]
    stem = STEMS[previous]
    native = flow / 'results' / platform / design / f'run_{slot}'
    expected = {f'flow/results/{stem}.{suffix}': digest(native / f'{stem}.{suffix}')
                for suffix in ('odb', 'sdc')}
    matches = []
    for path in state.glob(f'iteration-{iteration}/slot-*-{previous}.json'):
        value = json.loads(path.read_text())
        if value['campaign_id'] != campaign or value.get('status') != 'succeeded':
            continue
        if donor_slot is not None and value['candidate_slot'] != donor_slot:
            continue
        artifacts = {row['store_key']: row for row in value['artifacts']}
        if all(name in artifacts and artifacts[name]['sha256'] == sha
               for name, sha in expected.items()):
            matches.append(value)
    if not matches:
        raise ValueError('Native checkpoint has no successful EF producer with matching ODB/SDC.')
    # Equal checkpoint bytes may occur in distinct slots. Prefer the local slot;
    # otherwise pick a deterministic producer and preserve its actual identity.
    matches.sort(key=lambda value: (value['candidate_slot'] != slot, value['candidate_slot']))
    return matches[0]


def project_archive(archive_path, flow, platform, design, slot):
    """Project only this candidate's registered outputs back to native A2 paths."""
    names = set()
    with tempfile.TemporaryDirectory(dir=archive_path.parent) as temporary:
        root = Path(temporary)
        for name in ('results', 'logs', 'objects', 'reports'):
            (root / name).mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                path = Path(entry.filename)
                if (path.is_absolute() or '..' in path.parts or len(path.parts) < 2
                        or path.parts[0] != 'flow'
                        or path.parts[1] not in {'results', 'logs', 'objects', 'reports', 'combined.log'}
                        or (path.parts[1] == 'combined.log' and len(path.parts) != 2)
                        or stat.S_ISLNK(entry.external_attr >> 16) or path.as_posix() in names):
                    raise ValueError('Invalid registered native archive member: ' + entry.filename)
                names.add(path.as_posix())
                target = root / Path(*path.parts[1:])
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, target.open('wb') as destination:
                        shutil.copyfileobj(source, destination)
        if not (root / 'combined.log').is_file():
            raise ValueError('Registered native archive has no combined stage log.')
        for name in ('results', 'logs', 'objects', 'reports'):
            target = flow / name / platform / design / f'run_{slot}'
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(root / name, target)
        combined = flow / 'logs' / f'{platform}_{design}_run{slot}.log'
        temporary_log = combined.with_suffix('.platform.log')
        shutil.copy2(root / 'combined.log', temporary_log)
        os.replace(temporary_log, combined)


class PlatformExecution:
    def __init__(self, client, flow, state, profile, campaign, threads, timeout_seconds,
                 resources=None):
        self.client = client
        self.flow = Path(flow).resolve()
        self.state = Path(state).resolve()
        self.profile = Path(profile).resolve()
        self.campaign = campaign
        self.threads = threads
        self.timeout = timeout_seconds
        self.resources = resources
        self.request_resources = ResourceRequest(cpu_cores=threads, **(
            resources if resources is not None else {'memory_bytes': 6 << 30, 'processes': 256}))

    def execute(self, *, iteration, slot, candidate_id, platform, design, stage,
                config=None, sdc=None, evaluation=None, donor_slot=None):
        path = self.state / f'iteration-{iteration}/slot-{slot}-{stage}.json'
        hashes = {'profile': digest(self.profile)}
        if os.environ.get('EDA_PLATFORM_OBJECTIVE'):
            hashes['shared_objective'] = digest(Path(os.environ['EDA_PLATFORM_OBJECTIVE']))
        if os.environ.get('EDA_PLATFORM_CONTEXT'):
            hashes['design_context'] = digest(Path(os.environ['EDA_PLATFORM_CONTEXT']))
        if not stage.startswith('eval_'):
            hashes.update(config=digest(config), sdc=digest(sdc))
        identity = {'campaign_id': self.campaign, 'iteration': iteration,
                    'candidate_slot': slot, 'candidate_id': candidate_id,
                    'platform': platform, 'design': design, 'stage': stage,
                    'input_hashes': hashes, 'evaluation': evaluation,
                    'threads': self.threads, 'timeout_seconds': self.timeout,
                    'donor_slot': donor_slot}
        if self.resources is not None:
            identity['resources'] = self.request_resources.to_dict()
        if path.exists():
            record = json.loads(path.read_text())
            if any(record[key] != value for key, value in identity.items()):
                raise ValueError('Saved native task inputs or candidate identity changed.')
        else:
            inputs = {'adapter': 'a2_stage', 'stage': stage, 'threads': self.threads,
                      'profile_path': 'inputs/profile.json'}
            staged = []
            for source, destination in [(self.profile, 'inputs/profile.json')] + (
                    [] if stage.startswith('eval_') else
                    [(config, 'inputs/candidate.mk'), (sdc, 'inputs/candidate.sdc')]):
                uploaded = self.client.upload_input(Path(source).read_bytes())
                staged.append(InputFile(input_id=uploaded['input_id'], destination=destination))
            labels = {'campaign_id': self.campaign, 'iteration': str(iteration),
                      'candidate_id': candidate_id, 'candidate_slot': str(slot), 'stage': stage}
            if (self.resources is not None and self.request_resources.memory_bytes is not None
                    and self.request_resources.memory_bytes > 6 << 30):
                labels['memory_approval'] = 'manual'
            parent = None
            if stage != 'place':
                parent = find_predecessor(self.state, self.flow, self.campaign,
                                          iteration, platform, design, slot, stage, donor_slot)
                archive = next(row for row in parent['artifacts'] if row['kind'] == 'flow_archive')
                inputs['checkpoint_path'] = 'inputs/checkpoint.zip'
                staged.append(InputFile(artifact_id=archive['artifact_id'], destination='inputs/checkpoint.zip'))
            if stage.startswith('eval_'):
                inputs['evaluation'] = evaluation
                labels.update(run_type='analysis', analysis_of_run_id=parent['run_id'])
            else:
                inputs.update(config_path='inputs/candidate.mk', sdc_path='inputs/candidate.sdc')
            key = f'{self.campaign}:{iteration}:{slot}:{candidate_id}:{stage}'
            task = TaskSpec(task_id=f'a2-{iteration}-{slot}-{stage}', project_id='a2-flow',
                            design_id=design, experiment_id=self.campaign, plugin_id='openroad-data',
                            inputs=inputs, staged_inputs=tuple(staged), labels=labels,
                            timeout_seconds=self.timeout,
                            resources=self.request_resources)
            spec = task.to_dict()
            if os.environ.get('EDA_PLATFORM_OBJECTIVE'):
                from eda_toolkits.objectives import bind_task_objective

                bind_task_objective(spec)
            if os.environ.get('EDA_PLATFORM_CONTEXT'):
                from eda_toolkits.context import bind_task_context

                bind_task_context(spec)
            record = {**identity, 'idempotency_key': key, 'task': spec,
                      'parent_run_id': None if parent is None else parent['run_id'],
                      'status': 'prepared'}
            write_record(path, record)
        # The exact persisted request is reused if interruption lost the submit reply.
        run = (self.client.run(record['run_id']) if 'run_id' in record else
               self.client.submit(record['task'], idempotency_key=record['idempotency_key'])['run'])
        gate = os.environ.get('DRP_ACCEPTANCE_SUBMIT_GATE')
        if ('run_id' not in record and gate == f'{iteration}:{slot}:{stage}'):
            write_record(self.state / 'submit-acceptance-gate.json', {
                'run_id': run['run_id'], 'idempotency_key': record['idempotency_key'],
                'record_path': str(path), 'pid': os.getpid()})
            while not (self.state / 'release-submit-acceptance-gate').exists():
                time.sleep(.2)
        record.update(run_id=run['run_id'], status=run['status'])
        write_record(path, record)
        deadline = time.monotonic() + self.timeout
        while run['status'] not in TERMINAL:
            if time.monotonic() >= deadline:
                self.client.cancel(run['run_id'])
                raise TimeoutError('Native task exceeded its queue-and-execution budget.')
            time.sleep(.5)
            run = self.client.run(run['run_id'])
        record.update(status=run['status'], terminal_run=run,
                      artifacts=self.client.artifacts(run['run_id']))
        write_record(path, record)
        if run['status'] != 'succeeded':
            raise RuntimeError(f'Native {stage} task {run["run_id"]} ended {run["status"]}.')
        if stage.startswith('eval_'):
            artifact = next(row for row in record['artifacts'] if row['kind'] == 'extractor_log')
            destination = self.flow / 'logs' / f'eval_tns_{stage[5:]}_run{slot}.log'
            destination.write_bytes(self.client.artifact_bytes(run['run_id'], artifact['artifact_id']))
        else:
            artifact = next(row for row in record['artifacts'] if row['kind'] == 'flow_archive')
            destination = path.with_suffix('.zip')
            self.client.materialize_artifact(run['run_id'], artifact['artifact_id'],
                                             str(destination))
            if digest(destination) != artifact['sha256']:
                raise ValueError('Registered stage archive hash does not match downloaded bytes.')
            project_archive(destination, self.flow, platform, design, slot)
        return record

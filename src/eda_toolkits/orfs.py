"""Public ORFS task construction and fixed-input snapshot export."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import uuid

from .inputs import FileChunks


class OrfsToolkit:
    def __init__(self, client, config, assets_root):
        self.client, self.config = client, dict(config)
        self.assets_root = Path(assets_root).resolve()

    def submit_flow(self, design='gcd', platform='nangate45', revision=None):
        if (platform, design) != ('nangate45', 'gcd'):
            raise ValueError('this release supports the verified Nangate45/GCD ORFS profile')
        revision = revision or 'flow-' + uuid.uuid4().hex[:12]
        task = {'schema_version':3, 'task_id':revision, 'project_id':'orfs-flow',
                'design_id':design, 'plugin_id':'openroad-data',
                'inputs':{**self.config, 'adapter':'orfs_flow', 'threads':8,
                          'revision_id':revision, 'design_config':f'designs/{platform}/{design}/config.mk'},
                'labels':{'memory_approval':'manual'},
                'resources':{'cpu_cores':8, 'memory_bytes':24*1024**3, 'processes':256},
                'timeout_seconds':3600, 'max_attempts':1, 'expected_artifacts':['flow_archive']}
        return self.client.submit(task)

    def export_flow(self, run_id, snapshot_id):
        run = self.client.run(run_id)
        if run['status'] != 'succeeded':
            raise ValueError('only a completed successful flow can be exported')
        artifacts = self.client.artifacts(run_id)
        inputs, staged = {}, []
        fields = {'6_final.odb':'odb_path', '6_final.sdc':'sdc_path', '6_final.spef':'spef_path'}
        for name, field in fields.items():
            matches = [a for a in artifacts if Path(a['store_key']).name == name]
            if len(matches) != 1:
                raise ValueError('flow export requires one registered final artifact: '+name)
            destination = 'inputs/' + name
            staged.append({'artifact_id':matches[0]['artifact_id'], 'destination':destination})
            inputs[field] = destination
        self.assets_root.mkdir(parents=True, exist_ok=True)
        library = self.assets_root / 'NangateOpenCellLibrary_typical.lib'
        command = [self.config.get('container_runtime','apptainer'), 'exec', '--cleanenv', '--containall',
                   '--bind',f'{self.assets_root}:/asset-out',self.config['orfs_image'], 'cp',
                   '/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib',
                   '/asset-out/NangateOpenCellLibrary_typical.lib']
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        uploaded = self.client.upload_input_chunks(FileChunks(library))
        staged.append({'input_id':uploaded['input_id'], 'destination':'inputs/library.lib'})
        inputs.update(liberty_paths=['inputs/library.lib'], adapter='openroad',
                      openroad_bin=self.config['openroad_bin'], snapshot_id=snapshot_id,
                      design_id=run['design_id'], revision_id=run['task_id'], run_id=run_id,
                      stage='finish', created_at=datetime.now(timezone.utc).isoformat(),
                      output_directory='query-data', parasitic_mode='spef', ideal_clocks=False,
                      path_count=20, endpoint_path_count=1, unit='s', corner='typical', analysis='default')
        task = {'schema_version':3,'task_id':snapshot_id,'project_id':'orfs-export',
                'design_id':run['design_id'],'plugin_id':'openroad-data', 'inputs':inputs,
                'staged_inputs':staged, 'labels':{'run_type':'analysis','analysis_of_run_id':run_id},
                'resources':{'cpu_cores':2,'memory_bytes':6*1024**3,'processes':128},
                'timeout_seconds':180,'max_attempts':1,'expected_artifacts':['data_snapshot']}
        return self.client.submit(task)

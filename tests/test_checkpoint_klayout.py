"""Relocated checkpoints must not reuse generated foreign LEF references."""

import zipfile

import pytest

from eda_toolkits.openroad.a2_checkpoint import clear_downstream, restore_checkpoint


@pytest.mark.parametrize('stage,stem', [('cts', '3_place'), ('route_finish', '4_cts')])
def test_only_derived_stream_technology_is_invalidated(tmp_path, stage, stem):
    archive = tmp_path / 'source.zip'
    originals = {
        f'flow/results/{stem}.odb': b'original physical input',
        f'flow/results/{stem}.sdc': b'original clock input',
        'flow/objects/klayout.lyt': b'<lef-files>/work/old/klayout_tech.lef</lef-files>',
        'flow/objects/klayout_wrap.lyt': b'<lef-files>/work/old/wrap.lef</lef-files>',
        'flow/objects/klayout_tech.lef': b'VIA VIA12\nEND VIA12\n',
        'flow/objects/other-template.lyt': b'caller-owned template',
        'flow/objects/copyright.txt': b'original attribution',
    }
    with zipfile.ZipFile(archive, 'w') as bundle:
        for name, data in originals.items():
            bundle.writestr(name, data)
    before = archive.read_bytes()
    flow = tmp_path / 'restored'
    restore_checkpoint(archive, flow)
    for name in ('results', 'logs', 'reports', 'objects'):
        (flow / name).mkdir(exist_ok=True)
    clear_downstream(flow, stage)
    assert archive.read_bytes() == before
    for name, data in originals.items():
        relative = name.removeprefix('flow/')
        if relative in ('objects/klayout.lyt', 'objects/klayout_wrap.lyt'):
            assert not (flow / relative).exists()
        else:
            assert (flow / relative).read_bytes() == data


def test_absent_generated_technology_does_not_prevent_stage_resume(tmp_path):
    flow = tmp_path / 'flow'
    for name in ('results', 'logs', 'reports', 'objects'):
        (flow / name).mkdir(parents=True)
    clear_downstream(flow, 'route_finish')
    assert not list((flow / 'objects').iterdir())

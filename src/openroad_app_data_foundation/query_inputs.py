"""Bind native query jobs to exactly the original artifacts of a snapshot."""


def snapshot_inputs(snapshot, with_timing=True):
    context = snapshot.get('run_summary', {}).get('timing_context')
    if not context or not context.get('executor'):
        raise ValueError('snapshot lacks its executable native context')
    inputs = {'openroad_bin': context['executor']}
    roles = {'raw_design_database': 'odb_path'}
    paths = {}
    if with_timing:
        paths = {context['constraints']: 'sdc_path', **{p: 'library' for p in context['libraries']}}
        if context.get('rc_script'): paths[context['rc_script']] = 'rc_script_path'
        if context.get('parasitics'): paths[context['parasitics']] = 'spef_path'
        inputs['parasitic_mode'] = context['parasitic_mode']
    staged, libraries = [], []
    for ref in snapshot.get('source_artifacts', []):
        key = roles.get(ref.get('category')) or paths.get(ref.get('logical_path'))
        if not key:
            continue
        path = ref['logical_path']
        staged.append({'destination': path, 'artifact_id': ref['artifact_id']})
        if key == 'library': libraries.append(path)
        else: inputs[key] = path
    if 'odb_path' not in inputs or (with_timing and set(libraries) != set(context['libraries'])):
        raise ValueError('snapshot lacks original native inputs')
    if with_timing: inputs['liberty_paths'] = libraries
    return inputs, staged

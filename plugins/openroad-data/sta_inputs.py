"""The actual standard-cell and macro libraries staged for a timing analysis."""
from pathlib import PurePosixPath


def library_paths(inputs):
    values = inputs.get('liberty_paths')
    if values is None:
        value = inputs.get('liberty_path')
        values = [] if value is None else [value]
    if not isinstance(values, list) or any(not isinstance(v, str) or not v
                                           for v in values):
        raise ValueError('inputs.liberty_paths must be a list of staged paths')
    for value in values:
        path = PurePosixPath(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('library paths must be relative staged paths')
    if len(values) != len(set(values)):
        raise ValueError('library paths must be unique')
    return values


def timing_commands(inputs, quote):
    lines = [f'read_liberty {quote(path)}' for path in library_paths(inputs)]
    for field, command in [('sdc_path', 'read_sdc'), ('rc_script_path', 'source'),
                           ('spef_path', 'read_spef'),
                           ('global_routing_segments_path', 'read_global_route_segments')]:
        value = inputs.get(field)
        if value is not None:
            path = PurePosixPath(value) if isinstance(value, str) else None
            if not value or path is None or path.is_absolute() or '..' in path.parts:
                raise ValueError(f'inputs.{field} must be a relative staged path')
            lines.append(f'{command} {quote(value)}')
    mode = inputs.get('parasitic_mode')
    if mode not in (None, 'spef', 'placement', 'global_routing'):
        raise ValueError('parasitic_mode must be spef|placement|global_routing')
    if mode == 'spef' and not inputs.get('spef_path'):
        raise ValueError('spef mode requires spef_path')
    if mode == 'placement':
        if not inputs.get('rc_script_path') or inputs.get('spef_path'):
            raise ValueError('placement mode requires rc_script_path and no spef_path')
        lines.append('estimate_parasitics -placement')
    if mode == 'global_routing':
        if not inputs.get('rc_script_path') or not inputs.get('global_routing_segments_path') or inputs.get('spef_path'):
            raise ValueError('global_routing mode requires RC and native segments, without SPEF')
        lines.append('estimate_parasitics -global_routing')
    return lines


def directed_options(inputs, quote):
    lines, options = [], []
    for key, flag in [('from_pin', '-from'), ('to_pin', '-to')]:
        name = inputs.get(key)
        if name is None:
            continue
        if not isinstance(name, str) or not name or len(name) > 4096:
            raise ValueError(f'{key} must be a non-empty native pin or port name')
        lines += [f'set {key} [get_pins -quiet [list {quote(name)}]]',
                  f'if {{[llength ${key}] == 0}} {{ set {key} [get_ports -quiet [list {quote(name)}]] }}',
                  f'if {{[llength ${key}] != 1}} {{ error "{key} must resolve to one pin or port" }}']
        options.append(f'{flag} ${key}')
    group = inputs.get('path_group')
    if group is not None:
        if not isinstance(group, str) or not group or len(group) > 4096:
            raise ValueError('path_group must be a non-empty string')
        options.append(f'-path_group [list {quote(group)}]')
    return lines, ' '.join(options)

"""Native OpenROAD engineering calculations and parsing."""
from pathlib import Path

def segment_totals(path, names, scale):
    """Read each selected net's complete sections; repeated/zero-length rows count."""
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise ValueError('global-route lengths require a positive original dbu_per_micron')
    selected, active, totals = None, False, {}
    with Path(path).open(encoding='utf-8') as stream:
        for line_number, text in enumerate(stream, 1):
            line = text.strip()
            if not line:
                continue
            if line == '(':
                if selected is None or active:
                    raise ValueError('invalid route section opening at line ' + str(line_number))
                active = True
                if selected in names:
                    value = totals.setdefault(selected, {'record_count': 0, 'same_layer_segment_count': 0,
                        'interlayer_transition_count': 0, 'layers': {}, 'source_sections': []})
                    value['source_sections'].append({'start_line': line_number - 1, 'end_line': None})
            elif line == ')':
                if not active:
                    raise ValueError('invalid route section closing at line ' + str(line_number))
                if selected in names:
                    totals[selected]['source_sections'][-1]['end_line'] = line_number
                selected, active = None, False
            elif not active:
                if selected is not None:
                    raise ValueError('route net name requires a section at line ' + str(line_number))
                selected = line.replace('\\', '')
            elif selected in names:
                fields = line.split()
                if len(fields) != 6:
                    raise ValueError('route record requires six columns at line ' + str(line_number))
                x1, y1, layer1, x2, y2, layer2 = fields
                x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
                value = totals[selected]
                value['record_count'] += 1
                if layer1 == layer2:
                    length = abs(x2 - x1) + abs(y2 - y1)
                    row = value['layers'].setdefault(layer1, {'wirelength_dbu': 0, 'segment_count': 0})
                    row['wirelength_dbu'] += length
                    row['segment_count'] += 1
                    value['same_layer_segment_count'] += 1
                else:
                    value['interlayer_transition_count'] += 1
    if active or selected is not None:
        raise ValueError('incomplete original route section')
    for value in totals.values():
        value['wirelength_um'] = sum(r['wirelength_dbu'] for r in value['layers'].values()) / scale
        value['layers'] = [{'layer': layer, 'wirelength_um': row['wirelength_dbu'] / scale,
                            'segment_count': row['segment_count']}
                           for layer, row in sorted(value['layers'].items(), key=lambda pair: (int(pair[0][1:]), pair[0]))]
    return totals



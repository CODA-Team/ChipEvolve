"""Compact configuration, library/SPEF headers and actual flow timing receipts."""
import re
from datetime import datetime
from pathlib import Path
from .artifacts import native_excerpt, _receipt_files


def source_text(store, snapshot_id, path, root, stop=None):
    chunks, offset = [], 0
    while True:
        page = native_excerpt(store, snapshot_id,
            {'path': path, 'offset': str(offset), 'max_bytes': '65536'}, Path(root))
        chunks.append(page['text'])
        text = ''.join(chunks)
        if stop:
            match = re.search(stop, text, re.M)
            if match:
                return text[:match.start()], page['source']
        if page['next_offset'] is None:
            return text, page['source']
        offset = page['next_offset']


def configuration(text):
    """Literal Make assignments, with continued lines joined; no expression execution."""
    logical = re.sub(r'[ \t]*\\[ \t]*\n[ \t]*', ' ', text)
    assignments = []
    values = {}
    for line in logical.splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*([?:+]?=)\s*(.*)$', line)
        if match:
            name, operator, value = match.groups()
            value = value.strip()
            assignments.append({'name': name, 'operator': operator, 'value': value})
            if operator == '+=':
                values[name] = (values.get(name, '') + ' ' + value).strip()
            elif operator != '?=' or name not in values:
                values[name] = value
    return {'variables': values, 'assignments': assignments,
            'value_basis': 'literal file declarations; variables and functions remain unexpanded'}


def library_header(text):
    header = {}
    for key in ('time_unit', 'voltage_unit', 'current_unit', 'leakage_power_unit'):
        match = re.search(r'^\s*' + key + r'\s*:\s*"?([^";]+)"?\s*;', text, re.M)
        header[key] = match.group(1).strip() if match else None
    cap = re.search(r'^\s*capacitive_load_unit\s*\(\s*([^)]*)\)', text, re.M)
    header['capacitive_load_unit'] = re.sub(r'\s+', '', cap.group(1)) if cap else None
    for field, key in [('nominal_voltage', 'nom_voltage'), ('nominal_temperature', 'nom_temperature')]:
        match = re.search(r'^\s*' + key + r'\s*:\s*([-+\d.eE]+)\s*;', text, re.M)
        header[field] = float(match.group(1)) if match else None
    return header


def flow_timing(text):
    """Keep each original stage once; cumulative tables update the same stage."""
    stages, total = {}, None
    for line in text.splitlines():
        match = re.match(r'^Total\s+(\d+)\s+(\d+)\s*$', line)
        if match:
            total = {'elapsed_s': int(match.group(1)), 'peak_mb': int(match.group(2))}
        if not re.match(r'^\d+(?:_\d+)?_[a-z_0-9]+\s', line):
            continue
        parts = line.split()
        extension = parts[1] if len(parts)>1 and parts[1].startswith('.') else ''
        body = parts[2 if extension else 1:]
        numbers = [int(value) for value in body if value.isdigit()]
        name = parts[0] + extension
        stages[name] = {'stage': name, 'elapsed_s': numbers[0] if numbers else None,
                        'peak_mb': numbers[1] if len(numbers)>1 else None}
    return {'stages': list(stages.values()), 'reported_total': total,
            'unavailable_timing': [name for name, row in stages.items() if row['elapsed_s'] is None]}


def source_metadata(store, snapshot_id, root):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context', {})
    manifest = context.get('producer', {}).get('artifacts', {})
    configs = [path for path in manifest if path.startswith('designs/') and path.endswith('/config.mk')]
    result = {'snapshot_id': snapshot_id, 'configuration': [], 'libraries': [], 'spef': None, 'flow_timing': None}
    for path in configs:
        text, ref = source_text(store, snapshot_id, path, root)
        result['configuration'].append({'source': ref, **configuration(text)})
    library_refs = [ref for ref in snapshot.get('source_artifacts', []) if ref.get('category') == 'raw_library']
    for library in library_refs:
        matches = [path for path, ref in manifest.items() if path.endswith('.lib') and ref['sha256']==library['sha256']]
        if not matches:
            raise KeyError('loaded library has no original manifest source')
        path = sorted(matches)[0]
        text, ref = source_text(store, snapshot_id, path, root, stop=r'^\s*cell\s*\(')
        result['libraries'].append({'file': Path(path).name, 'source': ref, 'header': library_header(text)})
    spefs = [path for path in manifest if path.endswith('/6_final.spef')]
    if spefs and context.get('parasitics'):
        text, ref = source_text(store, snapshot_id, spefs[0], root, stop=r'^\*NAME_MAP|^\*D_NET')
        header = {key: value.strip().replace('"', '') for key, value in
                  re.findall(r'^\*(\w+)\s+(.*)$', text, re.M)}
        result['spef'] = {'source': ref, 'header': header}
    receipts = _receipt_files(snapshot, Path(root))
    flow_log = 'receipts/' + snapshot['design_id'] + '.flow.log'
    if flow_log in receipts:
        text, ref = source_text(store, snapshot_id, flow_log, root)
        result['flow_timing'] = {'source': ref, **flow_timing(text)}
        marks = {}
        for line in context.get('producer', {}).get('status_log', []):
            for state in ('running', 'finished'):
                if line.endswith(state + ':' + snapshot['design_id']):
                    marks[state] = datetime.fromisoformat(line.split()[0])
        result['flow_timing']['wall_seconds'] = (
            (marks['finished'] - marks['running']).total_seconds() if len(marks) == 2 else None)
    return result

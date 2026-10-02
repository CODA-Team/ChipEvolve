"""Effective constraint declarations and native coverage, read from actual artifacts."""
import re
from collections import Counter
from .identity import snapshot_identity
from .metadata import clock_context
from .queries import _limit, _offset, _page


def _text(client, ref):
    chunks, offset = [], 0
    while offset < ref['size_bytes']:
        excerpt = client.artifact_excerpt(ref['run_id'], ref['artifact_id'],
                                          offset=offset, max_bytes=65536)
        text = excerpt['text']
        if not text:
            raise ValueError('source ended before its recorded size')
        chunks.append(text)
        offset += excerpt.get('returned_bytes', len(text.encode('utf-8')))
    return ''.join(chunks)


def constraint_context(store, client, snapshot_id, query):
    snapshot = store.snapshot(snapshot_id)
    refs = snapshot.get('source_artifacts', [])
    sdc = next((r for r in refs if r.get('logical_path', '').endswith('effective.sdc')), None)
    if sdc is None:
        sdc = next((r for r in refs if r.get('category') == 'raw_constraints'), None)
    if sdc is None:
        raise KeyError('snapshot has no constraints source')
    text = _text(client, sdc)
    declarations = {key: [] for key in ('clocks', 'generated', 'input_delay', 'output_delay',
                                       'uncertainty', 'latency', 'propagation', 'all')}
    commands = {'create_clock': 'clocks', 'create_generated_clock': 'generated',
                'set_input_delay': 'input_delay', 'set_output_delay': 'output_delay',
                'set_clock_uncertainty': 'uncertainty', 'set_clock_latency': 'latency',
                'set_propagated_clock': 'propagation'}
    for line in text.splitlines():
        if line.strip() and not line.strip().startswith('#'):
            declarations['all'].append(line.strip())
        command = line.strip().split(' ', 1)[0]
        if command in commands:
            declarations[commands[command]].append(line.strip())
    report = next((r for r in refs if r.get('logical_path', '').endswith('check_setup.rpt')), None)
    coverage_text = _text(client, report) if report is not None else None
    count, endpoints = None, []
    if coverage_text is not None:
        match = re.search(r'There (?:are|is) (\d+) unconstrained endpoints?\.', coverage_text)
        if match:
            count = int(match[1])
            for line in coverage_text[match.end():].splitlines():
                if line.strip() and not line.startswith((' ', '\t')):
                    break
                if line.strip():
                    endpoints.append(line.strip())
        elif not coverage_text.strip() or 'unconstrained' not in coverage_text.lower():
            count = 0
    ports = store.filtered(snapshot_id, 'entities',
                           where="record_id GLOB 'bterm:*'")
    undeclared, port_coverage = {}, {}
    for direction, kind in [('INPUT', 'input_delay'), ('OUTPUT', 'output_delay')]:
        names = set()
        for line in declarations[kind]:
            match = re.search(r'\[get_ports\s+\{([^}]*)\}', line)
            if match:
                names.update(match[1].split())
        actual = {row['name'] for row in ports
                  if row.get('attributes', {}).get('direction') == direction}
        undeclared[kind] = sorted(actual - names)
        port_coverage[kind] = {'direction': direction, 'port_count': len(actual),
                               'ports_with_explicit_delay_count': len(actual & names),
                               'ports_without_explicit_delay_count': len(actual - names)}
    delay_values, clocks = {}, set()
    for kind in ('input_delay', 'output_delay'):
        values = set()
        for line in declarations[kind]:
            match = re.search(r'^set_\w+_delay\s+([-+\d.eE]+)', line)
            if match:
                values.add(float(match[1]))
            match = re.search(r'\[get_clocks\s+\{?([^}\]]+)\}?\]', line)
            if match:
                clocks.update(match[1].split())
        delay_values[kind] = sorted(values)
    limit, offset = _limit(query), _offset(query)
    context = snapshot.get('run_summary', {}).get('timing_context', {})
    manifest = context.get('producer', {}).get('artifacts', {})
    original_constraints = [{'staged_source': ref,
        'original_paths': sorted(path for path, item in manifest.items()
            if path.endswith('.sdc') and item['sha256'] == ref['sha256'])}
        for ref in refs if ref.get('logical_path') == context.get('constraints')]
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'clocks': clock_context(context).get('clocks', []), 'analysis': context.get('analysis'),
              'clock_source_semantics': 'clock sources are native ports/pins; source file citations are separate',
              'original_constraints': original_constraints,
              'corner': context.get('corner'), 'parasitic_mode': context.get('parasitic_mode'),
              'libraries': context.get('libraries', []),
              'declaration_counts': {key: len(rows) for key, rows in declarations.items()},
              'delay_values': delay_values, 'delay_value_unit': 'SDC/liberty time unit',
              'referenced_clocks': sorted(clocks), 'ports_without_delay': undeclared,
              'port_delay_coverage': port_coverage,
              'other_port_directions': dict(sorted(Counter(
                  row.get('attributes', {}).get('direction') for row in ports
                  if row.get('attributes', {}).get('direction') not in ('INPUT', 'OUTPUT')).items())),
              'port_delay_coverage_basis': 'unique native ports with explicit declarations in the selected SDC; clock ports included; absence is not a violation',
              'unconstrained_endpoint_count': count,
              'unconstrained_endpoints': endpoints[offset:offset + limit],
              'coverage_scope': 'native check_setup -verbose over this snapshot',
              'coverage_available': coverage_text is not None,
              'evidence': [sdc, *([report] if report else [])]}
    wanted = query.get('kind', 'clocks')
    if wanted not in declarations:
        raise ValueError('kind must be clocks|generated|input_delay|output_delay|uncertainty|latency|propagation|all')
    rows = declarations[wanted]
    result.update({'kind': wanted, 'declarations': rows[offset:offset + limit],
                   **_page(len(rows), len(rows[offset:offset + limit]), limit, offset)})
    return result

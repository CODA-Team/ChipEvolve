"""Complete ranked routing-grid facts from a declared native TSV report."""
import math
import re
from functools import lru_cache
from pathlib import Path

from .artifacts import native_excerpt, native_files
from .identity import snapshot_identity
from .queries import _limit, _offset, _page


def _layer_order(name):
    match = re.fullmatch(r'(.*?)(\d+)', name)
    return (match[1], int(match[2])) if match else (name, -1)


@lru_cache(maxsize=16)
def _rank(path, size, mtime_ns, layers, page_end):
    """Scan every matching row, retaining only the requested ranked prefix."""
    ranked, count, overflow_count, total_overflow = [], 0, 0, 0.0
    xs, ys, layer_counts = set(), set(), {}
    with Path(path).open() as stream:
        for line_number, line in enumerate(stream, 1):
            values = line.rstrip('\n').split('\t')
            if len(values) != 8:
                raise ValueError('congestion TSV must have eight columns; line ' + str(line_number))
            layer = values[0]
            xi, yi, x, y = map(int, values[1:5])
            capacity, usage, overflow = map(float, values[5:])
            if (min(capacity, usage, overflow) < 0 or
                    not all(math.isfinite(v) for v in (capacity, usage, overflow)) or
                    not math.isclose(overflow, max(0, usage - capacity), abs_tol=1e-9)):
                raise ValueError('invalid native congestion quantities; line ' + str(line_number))
            xs.add(x); ys.add(y)
            if layers and layer not in layers:
                continue
            count += 1
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            overflow_count += overflow > 0
            total_overflow += overflow
            utilization = usage / capacity if capacity else 0.0
            order = (-overflow, -utilization, _layer_order(layer), xi, yi)
            # Native grids contain each layer/index tuple once. The line number
            # gives a deterministic final order if the source repeats a tuple.
            item = (order, line_number, (layer, xi, yi, x, y, capacity, usage, overflow, utilization))
            if len(ranked) < page_end:
                ranked.append(item)
                if len(ranked) == page_end:
                    ranked.sort(reverse=True)
            elif item < ranked[0]:
                ranked[0] = item
                ranked.sort(reverse=True)
    return (sorted(ranked), sorted(xs), sorted(ys), count, overflow_count,
            total_overflow, layer_counts)


def congestion_grid(store, snapshot_id, query, root):
    allowed = {'file', 'layers', 'limit', 'offset', 'fields', 'detail'}
    if set(query) - allowed:
        raise ValueError('congestion accepts file,layers,limit,offset,fields,detail')
    snapshot = store.snapshot(snapshot_id)
    file = query.get('file')
    if not file:
        name = snapshot['stage'] + '.congestion.tsv'
        catalog = native_files(store, snapshot_id,
            {'kind': 'reports', 'name_contains': name, 'limit': '1'}, Path(root))['files']
        if catalog['count'] != 1 or Path(catalog['items'][0]['relative_path']).name != name:
            raise ValueError('file must select an original eight-column congestion TSV; '
                             'no unique report for snapshot stage ' + snapshot['stage'])
        file = catalog['items'][0]['relative_path']
    source = native_excerpt(store, snapshot_id, {'path': file, 'max_bytes': '1'}, Path(root))['source']
    stat = Path(source['path']).stat()
    layers = tuple(sorted(set(query['layers'].split(',')))) if query.get('layers') else ()
    limit, offset = _limit(query), _offset(query)
    ranked, xs, ys, count, over_count, overflow, layer_counts = _rank(
        source['path'], stat.st_size, stat.st_mtime_ns, layers, limit + offset)
    summary = snapshot['run_summary']
    scale, die = summary['dbu_per_micron'], summary['die_bbox']
    x_end = dict(zip(xs, xs[1:] + [die['x_max']]))
    y_end = dict(zip(ys, ys[1:] + [die['y_max']]))
    cells = []
    for _, line_number, row in ranked[offset:offset + limit]:
        layer, xi, yi, x, y, capacity, usage, over, utilization = row
        box = [x, y, x_end[x], y_end[y]]
        cells.append({'layer': layer, 'x_index': xi, 'y_index': yi,
            'capacity': capacity, 'usage': usage, 'overflow': over,
            'utilization': utilization, 'bbox_dbu': box, 'bbox_um': [v / scale for v in box],
            'source_line': line_number})
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
        'cells': cells, 'layers': layers or sorted(layer_counts, key=_layer_order),
        'cell_counts_by_layer': layer_counts, 'overflow_cell_count': over_count,
        'total_overflow': overflow, 'dbu_per_micron': scale,
        'ranking': 'overflow desc, utilization desc (zero capacity uses zero), natural layer name asc, x/y index asc',
        'coverage_scope': 'every native TSV row in the requested layers; ranked pages retain complete counts',
        'bbox_basis': 'adjacent native grid coordinates; final edge uses original die boundary',
        'source': source, **_page(count, len(cells), limit, offset)}

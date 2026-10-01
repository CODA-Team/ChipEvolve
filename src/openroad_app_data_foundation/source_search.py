"""Locate facts in original text without sending whole engineering reports."""
from collections import deque
from pathlib import Path
import re

from .artifacts import native_excerpt
from .queries import _limit, _offset, _page


def search_source(store, snapshot_id, query, root):
    allowed = {'path', 'pattern', 'ignore_case', 'context_lines', 'limit', 'offset'}
    if set(query) - allowed:
        raise ValueError('unknown source search field')
    pattern = query.get('pattern')
    if not pattern or len(pattern) > 4096:
        raise ValueError('pattern must be a nonempty regular expression up to 4096 characters')
    if query.get('ignore_case', '0') not in ('0', '1'):
        raise ValueError('ignore_case must be 0|1')
    try:
        expression = re.compile(pattern, re.I if query.get('ignore_case') == '1' else 0)
    except re.error as exc:
        raise ValueError('invalid source search pattern: ' + str(exc)) from exc
    context = int(query.get('context_lines', 0))
    if not 0 <= context <= 10:
        raise ValueError('context_lines must be between 0 and 10')
    limit, offset = _limit({**query, 'limit': query.get('limit', '20')}), _offset(query)
    source = native_excerpt(store, snapshot_id, {'path': query.get('path'), 'max_bytes': '1'}, Path(root))['source']
    previous, active, matches = deque(maxlen=context), [], []
    count, byte_offset = 0, 0
    with Path(source['path']).open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            line = {'line': number, 'start': byte_offset, 'end': byte_offset + len(raw),
                    'text': raw.decode('utf-8', errors='replace')}
            byte_offset += len(raw)
            for item in active:
                item['lines'].append(line)
            active = [item for item in active if number < item['match_line'] + context]
            if expression.search(line['text']):
                if offset <= count < offset + limit:
                    item = {'match_line': number, 'match_byte_offset': line['start'],
                            'lines': [*previous, line]}
                    matches.append(item)
                    if context:
                        active.append(item)
                count += 1
            previous.append(line)
    for item in matches:
        lines = item.pop('lines')
        item.update(line_start=lines[0]['line'], line_end=lines[-1]['line'],
                    byte_start=lines[0]['start'], byte_end=lines[-1]['end'],
                    text=''.join(line['text'] for line in lines))
    return {'snapshot_id': snapshot_id, 'source': source, 'pattern': pattern,
            'matches': matches, **_page(count, len(matches), limit, offset),
            'coverage_scope': 'all lines in this original file; offsets count matching lines'}


def source_lines(store, snapshot_id, query, root):
    """Read a requested inclusive line range from the actual full source file."""
    start = int(query.get('start_line', 1))
    end = int(query.get('end_line', start + 79))
    maximum = int(query.get('max_bytes', 8192))
    if start < 1 or end < start or not 1 <= maximum <= 65536:
        raise ValueError('line range must be positive/increasing and max_bytes between 1 and 65536')
    source = native_excerpt(store, snapshot_id, {'path': query.get('path'), 'max_bytes': '1'}, Path(root))['source']
    chunks, byte_offset, first_offset, last_line, partial, returned = [], 0, None, None, False, 0
    with Path(source['path']).open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number < start:
                byte_offset += len(raw)
                continue
            if number > end:
                break
            if first_offset is None:
                first_offset = byte_offset
            chunk = raw[:maximum - returned]
            chunks.append(chunk)
            returned += len(chunk)
            byte_offset += len(chunk)
            last_line = number
            partial = len(chunk) < len(raw)
            if partial or returned == maximum:
                break
    if first_offset is None:
        raise KeyError('requested start_line is outside the original source')
    complete = last_line == end and not partial
    return {'snapshot_id': snapshot_id, 'source': source, 'text': b''.join(chunks).decode('utf-8', errors='replace'),
            'offset': first_offset, 'returned_bytes': byte_offset - first_offset,
            'truncated': not complete, 'next_offset': byte_offset if not complete and byte_offset < source['size_bytes'] else None,
            'requested_start_line': start, 'requested_end_line': end, 'line_start': start, 'line_end': last_line,
            'line_end_complete': not partial, 'range_complete': complete,
            'coverage_scope': 'actual inclusive original line range; next_offset continues original bytes when bounded'}

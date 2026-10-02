"""Complete ordered read batches, including dependencies on earlier real results."""
import re
import json
import urllib.parse

from openroad_platform_client import KernelError, KernelUnavailable
from openroad_platform_contracts import ContractError
from .envelope import envelope, error_envelope
from .resolved_timing import timing_request


def _pointer(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('binding pointer must be an absolute JSON pointer')
    for part in pointer[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not part.isdecimal() or int(part) >= len(value):
                raise ValueError('binding pointer has an invalid array index: ' + part)
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ValueError('binding pointer does not resolve: ' + pointer)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ValueError('binding pointer must resolve to a non-null string or number')
    return urllib.parse.quote(str(value), safe='')


def read_batch(body, get):
    requests, bindings = body.get('requests'), body.get('bindings', {})
    if not isinstance(requests, list) or not 1 <= len(requests) <= 20 or not all(
            isinstance(path, str) and (path.split('?', 1)[0] == '/snapshots' or
                path.startswith(('/snapshots/', '/runs/'))) and
            not urllib.parse.urlparse(path).netloc for path in requests):
        raise ValueError('requests must contain 1 to 20 local snapshot/run query paths')
    if not isinstance(bindings, dict) or any(not re.fullmatch(r'[A-Za-z_]\w*', name) for name in bindings):
        raise ValueError('bindings must be a mapping of variable names')
    results, completed_queries = [], {}
    for index, path in enumerate(requests):
        try:
            def substitute(match):
                name = match[1]
                spec = bindings.get(name)
                if not isinstance(spec, dict) or set(spec) != {'request', 'pointer'}:
                    raise ValueError('binding requires request and pointer: ' + name)
                source = spec['request']
                if not isinstance(source, int) or isinstance(source, bool) or not 0 <= source < index:
                    raise ValueError('binding must refer to an earlier request: ' + name)
                if results[source]['status'] in ('not_found', 'unavailable'):
                    raise ValueError('binding source request failed: ' + name)
                return _pointer(results[source], spec['pointer'])
            resolved = re.sub(r'\{([A-Za-z_]\w*)\}', substitute, path)
            parsed = urllib.parse.urlparse(resolved)
            query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
            parts = parsed.path.strip('/').split('/')
            key = None
            if len(parts) == 3 and parts[0] == 'snapshots' and parts[2] == 'timing-overview' and query.get('resolve') == '1':
                native, _ = timing_request(query)
                key = (parts[1], json.dumps(native, sort_keys=True))
            if key is not None and key in completed_queries:
                execution = completed_queries[key]
                child_path = '/snapshots/' + execution['query_snapshot_id'] + '/timing-overview'
                options = {k: v for k, v in query.items() if k not in ('resolve', 'wait_seconds', 'endpoint_path_count')}
                options['check'] = query.get('check', 'setup')
                payload = get(child_path, options)
                payload['query_execution'] = {**execution, 'reuse_scope': 'one fresh native analysis within this read batch'}
            else:
                payload = get(parsed.path, query)
                execution = payload.get('query_execution')
                if key is not None and execution and execution['status'] == 'succeeded':
                    completed_queries[key] = execution
            result = envelope(parsed.path, query, payload)
        except KeyError as exc:
            result = error_envelope(path.split('?', 1)[0], 'not_found', str(exc.args[0]))
        except (ValueError, ContractError, KernelUnavailable, KernelError) as exc:
            result = error_envelope(path.split('?', 1)[0], 'unavailable', f'{type(exc).__name__}: {exc}')
        results.append(result)
    return {'results': results, 'failed_query_count': sum(
        item['status'] in ('not_found', 'unavailable') for item in results)}

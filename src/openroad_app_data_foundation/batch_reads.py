"""Complete ordered read batches, including dependencies on earlier real results."""
import re
import urllib.parse

from openroad_platform_client import KernelError, KernelUnavailable
from openroad_platform_contracts import ContractError
from .envelope import envelope, error_envelope


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
    results = []
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
            payload = get(parsed.path, query)
            result = envelope(parsed.path, query, payload)
        except KeyError as exc:
            result = error_envelope(path.split('?', 1)[0], 'not_found', str(exc.args[0]))
        except (ValueError, ContractError, KernelUnavailable, KernelError) as exc:
            result = error_envelope(path.split('?', 1)[0], 'unavailable', f'{type(exc).__name__}: {exc}')
        results.append(result)
    return {'results': results, 'failed_query_count': sum(
        item['status'] in ('not_found', 'unavailable') for item in results)}

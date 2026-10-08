"""One parser for native timing reports, normalization and requested pin names."""
import base64
import json
import sys
from pathlib import Path
from typing import Any

PATH_SECTIONS = ('source_clock_path', 'source_path', 'target_clock_path', 'target_path')


def checks(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, dict) and isinstance(payload.get('checks'), list):
        return [item for item in payload['checks'] if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get('paths'), list):
        return [item for item in payload['paths'] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def points(source: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for section in PATH_SECTIONS:
        rows = source.get(section, [])
        if isinstance(rows, list):
            result.extend({**item, 'path_section': section, 'section_index': i}
                          for i, item in enumerate(rows) if isinstance(item, dict))
    raw = source.get('points', [])
    if isinstance(raw, list):
        result.extend(item for item in raw if isinstance(item, dict))
    return result


def reported_pin_names(output_dir: Path) -> list[str]:
    names = set()
    for filename in ('timing_report.json', 'timing_report_hold.json'):
        rows = checks(json.loads((output_dir / filename).read_text()))
        if rows is None:
            raise ValueError('native report has no path collection: ' + filename)
        names.update(str(p.get('pin') or p.get('pin_name') or 'unknown')
                     for row in rows for p in points(row))
    return sorted(names)


if __name__ == '__main__':
    # Base64 transports exact names through Tcl without glob/list quoting loss.
    print(' '.join(base64.b64encode(name.encode()).decode()
                   for name in reported_pin_names(Path(sys.argv[1]))))

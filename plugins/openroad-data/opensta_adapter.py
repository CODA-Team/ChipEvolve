"""OpenSTA extraction plan and normalized timing-result writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def prepare(inputs: dict[str, Any], workspace: Path) -> dict[str, Any]:
    odb_path = _relative(inputs, "odb_path")
    output_name = _output_name(inputs)
    metadata = _metadata(inputs, "route")
    script = workspace / "opensta_extract.tcl"
    script.write_text(_script(inputs, odb_path, output_name), encoding="utf-8")
    binary = inputs.get("openroad_bin", "openroad")
    if not isinstance(binary, str) or not binary:
        raise ValueError("inputs.openroad_bin must be a non-empty string")
    return {"command": [binary, "-no_init", "-no_splash", "-exit", str(script)],
            "output_directory": output_name, "script_path": script.name,
            "metadata": metadata}


def normalize(output_dir: Path, inputs: dict[str, Any]) -> None:
    setup = output_dir / "timing_report.json"
    if not setup.is_file():
        raise ValueError("OpenSTA did not produce timing_report.json")
    metadata = _metadata(inputs, inputs.get("stage", "route"))
    mapping = _mapping(inputs, output_dir.parent)
    _write_json(output_dir / "manifest.json", {"snapshot": metadata, "schema_version": 3})
    # The setup (max) and hold (min) reports are both read here.  The
    # discriminator is the report's own path_type, not the constraint type:
    # ``type`` is "output_delay"/"check" while ``path_type`` is max/min.
    sources: list[tuple[dict[str, Any], str]] = []
    for filename in ("timing_report.json", "timing_report_hold.json"):
        candidate = output_dir / filename
        if not candidate.is_file():
            continue
        rows = _checks(json.loads(candidate.read_text(encoding="utf-8")))
        if rows is None:
            continue
        sources.extend((row, filename) for row in rows if isinstance(row, dict))
    if not sources:
        _write_coverage(output_dir, "unsupported", "timing JSON has no paths list")
        return
    timing_paths: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for path_index, (source, filename) in enumerate(sources):
        path_id = str(source.get("path_id") or f"path:{path_index}")
        point_rows = _points(source)
        point_ids: list[str] = []
        for ordinal, point in enumerate(point_rows):
            if not isinstance(point, dict):
                continue
            point_id = str(point.get("point_id") or f"{path_id}:point:{ordinal}")
            point_ids.append(point_id)
            point_name = str(point.get("pin") or point.get("pin_name") or "unknown")
            native_mapping = mapping.get(point_id) or mapping.get(point_name) or {}
            points.append(_point(point_id, path_id, ordinal, point, native_mapping, inputs))
        timing_paths.append({
            "path_id": path_id,
            "snapshot_id": metadata["snapshot_id"],
            "analysis": _value(source, "analysis", "view", default=inputs.get("analysis")),
            "check": _check_name(source) or inputs.get("check"),
            "group": _value(source, "group", "path_group", default=inputs.get("group")),
            "path_type": source.get("path_type"),
            "startpoint": source.get("startpoint"),
            "endpoint": source.get("endpoint"),
            "slack": source.get("slack"),
            "delay": source.get("delay"),
            "required_time": source.get("required_time"),
            "margin": source.get("margin"),
            "unit": source.get("unit") or inputs.get("unit"),
            "corner": source.get("corner") or inputs.get("corner"),
            "point_ids": point_ids,
            "point_field_availability": {
                "required": "unavailable",
                "reason": ("OpenSTA report_checks does not emit a per-point required "
                           "field; required_time is reported per path"),
            },
            "evidence": [_timing_evidence(inputs, {"path_index": path_index,
                                                    "report": filename})],
        })
        for name in ("native_path_id", "structural_fingerprint"):
            if isinstance(source.get(name), str) and source[name]:
                timing_paths[-1][name] = source[name]
    _write_lines(output_dir / "timing_paths.jsonl", timing_paths)
    _write_lines(output_dir / "timing_points.jsonl", points)
    _write_json(output_dir / "manifest.json", {"snapshot": metadata, "schema_version": 3})
    _write_json(output_dir / "summary.json", {"snapshot": metadata,
                                                "timing_path_count": len(timing_paths)})
    _write_json(output_dir / "coverage.json", {
        "source": "opensta",
        "timing": "parsed" if timing_paths else "empty",
        "dbnetwork": "parsed" if mapping else "unsupported",
    })


def _check_name(source: dict[str, Any]) -> str | None:
    """setup/hold comes from path_type (max/min), never from `type`."""
    path_type = source.get("path_type")
    if path_type == "max":
        return "setup"
    if path_type == "min":
        return "hold"
    return None


def _point(point_id: str, path_id: str, ordinal: int, point: dict[str, Any],
           mapping: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    result = {"point_id": point_id, "path_id": path_id, "ordinal": ordinal,
              "pin_name": str(point.get("pin") or point.get("pin_name") or "unknown"),
              "instance_name": point.get("instance"),
              "net_name": point.get("net"),
              "cell_name": point.get("cell"),
              "x": point.get("x"), "y": point.get("y"),
              "arrival": point.get("arrival"), "required": point.get("required"),
              "slew": point.get("slew"), "load": point.get("capacitance"),
              "clock": point.get("clock"), "time_unit": point.get("time_unit"),
              "capacitance_unit": "F", "distance_unit": "m",
              "path_section": point.get("path_section")}
    for name in ("pin_id", "instance_id", "net_id", "object_id"):
        value = mapping.get(name)
        if value is not None:
            result[name] = value
    result["mapping_status"] = "mapped" if mapping else "unmapped"
    result["mapping_basis"] = "native_dbnetwork" if mapping else "none"
    result["evidence"] = [_timing_evidence(inputs, detail={"point": ordinal},
                                             artifact_id=point.get("artifact_id"))]
    return result


def _timing_evidence(inputs: dict[str, Any], detail: dict[str, Any],
                     *, artifact_id: Any = None) -> dict[str, Any]:
    """Reference a real artifact when supplied; otherwise preserve only its role."""
    value = artifact_id or inputs.get("timing_artifact_id")
    result = {
        "artifact_kind": "raw_timing_report",
        "logical_path": inputs.get("timing_artifact_path", "query-data/timing_report.json"),
        "source_type": "json",
        "detail": detail,
    }
    if isinstance(value, str) and value and value not in {"timing-report", "orfs-metadata"}:
        result["artifact_id"] = value
    return result


def _value(source: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = source.get(name)
        if value is not None and value != "":
            return value
    return default


def _checks(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, dict) and isinstance(payload.get("checks"), list):
        return [item for item in payload["checks"] if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("paths"), list):
        return [item for item in payload["paths"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _points(source: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for section in ("source_clock_path", "source_path", "target_path"):
        rows = source.get(section, [])
        if isinstance(rows, list):
            for item in rows:
                if isinstance(item, dict):
                    points.append({**item, "path_section": section})
    raw = source.get("points", [])
    if isinstance(raw, list):
        points.extend(item for item in raw if isinstance(item, dict))
    return points


def _script(inputs: dict[str, Any], odb_path: str, output_name: str) -> str:
    lines = [
        "# Generated by openroad-data/opensta_adapter.py.",
        "proc json_q {value} {",
        r'  set value [string map [list "\\" "\\\\" "\"" "\\\"" "\n" "\\n" "\r" "\\r" "\t" "\\t"] $value]',
        r'  return "\"$value\""',
        "}",
        "proc json_obj {args} {",
        '  set out "{"; set first 1',
        "  foreach {key value} $args {",
        '    if {!$first} { append out "," }',
        '    append out [json_q $key] ":" $value; set first 0',
        "  }",
        '  append out "}"; return $out',
        "}",
        f"file mkdir {_tcl(output_name)}",
        f"read_db {_tcl(odb_path)}",
    ]
    for option, command in (("liberty_path", "read_liberty"),
                            ("sdc_path", "read_sdc"), ("spef_path", "read_spef")):
        value = inputs.get(option)
        if value is not None:
            _require_relative(value, option)
            lines.append(f"{command} {_tcl(value)}")
    count = inputs.get("path_count", 5)
    if not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError("inputs.path_count must be an integer between 1 and 200")
    # Non-deprecated option names matter: -group_count / -endpoint_count print a
    # deprecation warning into the redirected file and break JSON parsing.
    for filename, delay in (("timing_report.json", "max"),
                            ("timing_report_hold.json", "min")):
        lines.append("sta::redirect_file_begin [file join "
                     f"{_tcl(output_name)} {_tcl(filename)}]")
        lines.append(f"report_checks -path_delay {delay} -group_path_count {count} "
                     f"-endpoint_path_count {count} -format json -digits 6")
        lines.append("sta::redirect_file_end")
    lines.append(_mapping_script(output_name))
    return "\n".join(lines) + "\n"


def _mapping_script(output_name: str) -> str:
    """Use OpenROAD's native sta_to_db conversion for every reported pin."""
    output = _tcl(output_name)
    return f'''proc db_pin_mapping {{sta_pin}} {{
  set db_pin [sta::sta_to_db_pin $sta_pin]
  set fields [list dbnetwork [json_q native] \
      pin_id [json_q "iterm:[$db_pin getId]"] \
      instance_id [json_q "inst:[[$db_pin getInst] getId]"] \
      instance_name [json_q [[$db_pin getInst] getName]]]
  set net [$db_pin getNet]
  if {{$net ne "NULL"}} {{
    lappend fields net_id [json_q "net:[$net getId]"] \
        net_name [json_q [$net getName]]
  }}
  return [json_obj {{*}}$fields]
}}
set db_mapping [list]
foreach sta_pin [get_pins -quiet *] {{
  set pin_name [sta::get_full_name $sta_pin]
  lappend db_mapping $pin_name [db_pin_mapping $sta_pin]
}}
foreach sta_port [get_ports -quiet *] {{
  set db_port [sta::sta_to_db_port $sta_port]
  set pin_name [sta::get_full_name $sta_port]
  set fields [list dbnetwork [json_q native] \
      pin_id [json_q "bterm:[$db_port getId]"] \
      pin_name [json_q [$db_port getName]]]
  set net [$db_port getNet]
  if {{$net ne "NULL"}} {{
    lappend fields net_id [json_q "net:[$net getId]"] \
        net_name [json_q [$net getName]]
  }}
  lappend db_mapping $pin_name [json_obj {{*}}$fields]
}}
set fd [open [file join {output} dbnetwork_map.json] w]
puts $fd [json_obj {{*}}$db_mapping]
close $fd'''


def _metadata(inputs: dict[str, Any], stage: str) -> dict[str, str]:
    result = {key: inputs.get(key) for key in (
        "snapshot_id", "design_id", "revision_id", "run_id", "created_at")}
    result["stage"] = inputs.get("stage", stage)
    missing = [key for key, value in result.items() if not isinstance(value, str) or not value]
    if missing:
        raise ValueError(f"inputs missing snapshot fields: {', '.join(missing)}")
    return {key: str(value) for key, value in result.items()}


def _relative(inputs: dict[str, Any], name: str) -> str:
    value = inputs.get(name)
    _require_relative(value, name)
    return value


def _require_relative(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value or value.startswith("/") \
            or ".." in Path(value).parts:
        raise ValueError(f"inputs.{name} must be a relative staged path")


def _output_name(inputs: dict[str, Any]) -> str:
    value = inputs.get("output_directory", "query-data")
    _require_relative(value, "output_directory")
    return value


def _tcl(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("[", "\\[").replace("]", "\\]")
    escaped = escaped.replace("$", "\\$")
    return f'"{escaped}"'


def _write_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_coverage(output_dir: Path, status: str, reason: str) -> None:
    _write_json(output_dir / "coverage.json", {"source": "opensta", "timing": status,
                                                "reason": reason})


def _mapping(inputs: dict[str, Any], workspace: Path) -> dict[str, dict[str, Any]]:
    value = inputs.get("dbnetwork_map_path")
    if value is None:
        output_name = inputs.get("output_directory", "query-data")
        _require_relative(output_name, "output_directory")
        candidate = workspace / output_name / "dbnetwork_map.json"
        if not candidate.is_file():
            return {}
        path = candidate
    else:
        _require_relative(value, "dbnetwork_map_path")
        path = workspace / value
    if not path.is_file():
        raise ValueError(f"dbNetwork mapping file is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dbNetwork mapping must be an object keyed by pin name")
    result: dict[str, dict[str, Any]] = {}
    for point_id, row in payload.items():
        if not isinstance(point_id, str) or not isinstance(row, dict):
            raise ValueError("dbNetwork mapping entries must be object values")
        result[point_id] = row
    return result

"""OpenSTA extraction plan and normalized timing-result writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sta_inputs import library_paths, timing_commands, directed_options
from timing_json import checks as _checks, points as _points


def prepare(inputs: dict[str, Any], workspace: Path) -> dict[str, Any]:
    odb_path = _relative(inputs, "odb_path")
    output_name = _output_name(inputs)
    metadata = _metadata(inputs, "route")
    script = workspace / "opensta_extract.tcl"
    (workspace / 'timing_json.py').write_bytes(Path(__file__).with_name('timing_json.py').read_bytes())
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
    #: (check, the file it came from, its index *within that file*).  The index
    #: matters: path:N is a global ordinal across both reports, so an evidence
    #: pointer that reuses it against one file names a row that file does not
    #: have - which is exactly what the evidence-recoverability check caught.
    sources: list[tuple[dict[str, Any], str, int]] = []
    for filename in ("timing_report.json", "timing_report_hold.json"):
        candidate = output_dir / filename
        if not candidate.is_file():
            continue
        rows = _checks(json.loads(candidate.read_text(encoding="utf-8")))
        if rows is None:
            continue
        sources.extend((row, filename, index)
                       for index, row in enumerate(rows) if isinstance(row, dict))
    if not sources:
        _write_coverage(output_dir, "unsupported", "timing JSON has no paths list")
        return
    timing_paths: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    for path_index, (source, filename, index_in_file) in enumerate(sources):
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
            points.append(_point(point_id, path_id, ordinal, point, native_mapping,
                                 inputs, filename, index_in_file))
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
            "data_arrival_time": source.get("data_arrival_time"),
            "crpr": source.get("crpr"),
            "source_clock": source.get("source_clock"),
            "target_clock": source.get("target_clock"),
            "source_clock_edge": source.get("source_clock_edge"),
            "target_clock_edge": source.get("target_clock_edge"),
            "unit": source.get("unit") or inputs.get("unit"),
            "corner": source.get("corner") or inputs.get("corner"),
            "point_ids": point_ids,
            "point_field_availability": {
                "required": "unavailable",
                "reason": ("OpenSTA report_checks does not emit a per-point required "
                           "field; required_time is reported per path"),
            },
            "evidence": [_timing_evidence(inputs,
                                          {"path_index": index_in_file,
                                           "report": filename},
                                          logical_path=f"query-data/{filename}")],
        })
        for name in ("native_path_id", "structural_fingerprint"):
            if isinstance(source.get(name), str) and source[name]:
                timing_paths[-1][name] = source[name]
    _write_lines(output_dir / "timing_paths.jsonl", timing_paths)
    _write_lines(output_dir / "timing_points.jsonl", points)
    _write_json(output_dir / "manifest.json", {"snapshot": metadata, "schema_version": 3})
    context_path = output_dir / "analysis_context.json"
    context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    context.update({"libraries": library_paths(inputs), "constraints": inputs.get("sdc_path"),
                    "rc_script": inputs.get("rc_script_path"),
                    "parasitics": inputs.get("spef_path"),
                    "parasitic_mode": inputs.get("parasitic_mode", "spef" if inputs.get("spef_path") else "unavailable"),
                    "analysis": inputs.get("analysis"), "corner": inputs.get("corner"),
                    "executor": inputs.get("openroad_bin"), "path_count_per_group": inputs.get("path_count", 5),
                    # How many paths per endpoint the report kept.  `1` means the
                    # N reported paths are N distinct endpoints, which is a
                    # different (and stronger) coverage claim than N variants of
                    # one endpoint, so the snapshot records which one it is.
                    "path_count_per_endpoint": inputs.get("endpoint_path_count", 1),
                    "endpoint_report": inputs.get("endpoint_path_count", 1) == 1,
                    "coverage_scope": "sampled report_checks paths; not all timing paths",
                    "parent_snapshot_id": inputs.get("parent_snapshot_id")})
    producer_path = inputs.get("producer_metadata_path")
    if producer_path:
        _require_relative(producer_path, "producer_metadata_path")
        context["producer"] = json.loads((output_dir.parent / producer_path).read_text())
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
    _write_json(summary_path, {**summary, "snapshot": metadata,
                              "timing_path_count": len(timing_paths), "timing_context": context})
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
           mapping: dict[str, Any], inputs: dict[str, Any],
           filename: str = "timing_report.json",
           path_index_in_file: int | None = None) -> dict[str, Any]:
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
    # A point has two sources and used to name neither correctly: it fell back to
    # the setup report even when it came from the hold report, and its `point`
    # ordinal had no path to attach to, so no point could be located at all.  The
    # same defect was fixed for timing_paths and missed here for 1510 rows.
    evidence = [_timing_evidence(
        inputs,
        {"path_index": path_index_in_file, "point": ordinal,
         "section": point.get("path_section"),
         "section_index": point.get("section_index"), "report": filename},
        artifact_id=point.get("artifact_id"),
        logical_path=f"query-data/{filename}")]
    if mapping:
        # pin_id / instance_id / net_id come from the dbnetwork map, not the report
        evidence.append({
            "artifact_kind": "raw_dbnetwork_map",
            "logical_path": "query-data/dbnetwork_map.json",
            "source_type": "json",
            # the map is keyed by pin name; naming the point id here would be
            # another pointer a caller cannot follow
            "detail": {"pin_name": str(point.get("pin") or point.get("pin_name") or "")},
        })
    result["evidence"] = evidence
    return result


def _timing_evidence(inputs: dict[str, Any], detail: dict[str, Any],
                     *, artifact_id: Any = None,
                     logical_path: str | None = None) -> dict[str, Any]:
    """Reference a real artifact when supplied; otherwise preserve only its role."""
    value = artifact_id or inputs.get("timing_artifact_id")
    result = {
        "artifact_kind": "raw_timing_report",
        "logical_path": logical_path or inputs.get(
            "timing_artifact_path", "query-data/timing_report.json"),
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
    lines.extend(timing_commands(inputs, _tcl))
    lines.append(_clock_script(output_name))
    count = inputs.get("path_count", 5)
    if not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError("inputs.path_count must be an integer between 1 and 200")
    # OpenSTA keeps at most this many paths *per endpoint*.  The default is 1:
    # "the N worst paths" means N distinct endpoints, which is the report the
    # reference flow produces (native_gold.tcl: -endpoint_path_count 1) and the
    # only reading of the question that is not a different question.  The old
    # default (== path_count) answered with N variants of a single endpoint.
    endpoints = inputs.get("endpoint_path_count", 1)
    if not isinstance(endpoints, int) or not 1 <= endpoints <= 200:
        raise ValueError(
            "inputs.endpoint_path_count must be an integer between 1 and 200")
    extra_lines, extra_options = directed_options(inputs, _tcl)
    lines.extend(extra_lines)
    # Non-deprecated option names matter: -group_count / -endpoint_count print a
    # deprecation warning into the redirected file and break JSON parsing.
    for filename, delay in (("timing_report.json", "max"),
                            ("timing_report_hold.json", "min")):
        lines.append("sta::redirect_file_begin [file join "
                     f"{_tcl(output_name)} {_tcl(filename)}]")
        lines.append(f"report_checks -path_delay {delay} -group_path_count {count} "
                     f"-endpoint_path_count {endpoints} {extra_options} "
                     f"-format json -digits 6")
        lines.append("sta::redirect_file_end")
    lines.append(_mapping_script(output_name))
    return "\n".join(lines) + "\n"


def _mapping_script(output_name: str) -> str:
    """Convert only pins actually present in the complete generated reports."""
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
proc db_port_mapping {{sta_port}} {{
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
  return [json_obj {{*}}$fields]
}}
set db_mapping [list]
set encoded_names [exec python3 timing_json.py {output}]
foreach encoded $encoded_names {{
  set pin_name [encoding convertfrom utf-8 [binary decode base64 $encoded]]
  set matches [get_pins -quiet [list $pin_name]]
  if {{[llength $matches] == 1}} {{
    lappend db_mapping $pin_name [db_pin_mapping [lindex $matches 0]]
  }} elseif {{[llength $matches] > 1}} {{
    error "reported pin name is ambiguous: $pin_name"
  }} else {{
    set ports [get_ports -quiet [list $pin_name]]
    if {{[llength $ports] == 1}} {{
      lappend db_mapping $pin_name [db_port_mapping [lindex $ports 0]]
    }} elseif {{[llength $ports] > 1}} {{
      error "reported port name is ambiguous: $pin_name"
    }} else {{
      puts "Unmapped reported pin: $pin_name"
    }}
  }}
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


def _clock_script(output_name: str) -> str:
    return f'''set clock_rows [list]
foreach clk [all_clocks] {{
  lappend clock_rows [json_obj name [json_q [get_name $clk]] \
      period [$clk period] period_ui [get_property $clk period] \
      unit [json_q s] propagated [$clk is_propagated] generated [$clk is_generated] \
      virtual [$clk is_virtual] waveform "\\[[join [$clk waveform] ,]\\]"]
}}
set fd [open [file join {_tcl(output_name)} analysis_context.json] w]
puts $fd [json_obj clocks "\\[[join $clock_rows ,]\\]"]
close $fd
write_sdc [file join {_tcl(output_name)} effective.sdc]
sta::redirect_file_begin [file join {_tcl(output_name)} check_setup.rpt]
check_setup -verbose
sta::redirect_file_end
'''

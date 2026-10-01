"""Native query/report bridge bound to original OpenROAD design inputs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sta_inputs import timing_commands, directed_options
from opendb_adapter import _tcl


REPORTS = {
    "native": ("native.rpt", None),
    "timing": ("timing.json", "report_checks -path_delay max -format json -digits 6"),
    "area": ("area.rpt", "report_design_area"),
    "power": ("power.json", "report_power -format json"),
}


def prepare(inputs: dict[str, Any], workspace: Path) -> dict[str, Any]:
    report_name = inputs.get("report")
    if not isinstance(report_name, str) or report_name not in REPORTS:
        raise ValueError(f"inputs.report must be one of: {', '.join(REPORTS)}")
    odb_path = _relative(inputs, "odb_path")
    output_name = _relative(inputs, "output_directory", default="reports")
    output_dir = workspace / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    report_name_on_disk, command = REPORTS[report_name]
    if report_name == "native":
        command = inputs.get("script")
        if not isinstance(command, str) or not command.strip() or len(command.encode()) > 65536:
            raise ValueError('native query script must be nonempty and at most 64 KiB')
    report_path = output_dir / report_name_on_disk
    script = workspace / "openroad_report.tcl"
    script.write_text(_script(inputs, odb_path, report_path, command), encoding="utf-8")
    binary = inputs.get("openroad_bin", "openroad")
    if not isinstance(binary, str) or not binary:
        raise ValueError("inputs.openroad_bin must be a non-empty string")
    return {
        "report": report_name,
        "report_path": report_path.relative_to(workspace).as_posix(),
        "script_path": script.name,
        "command": [binary, "-no_init", "-no_splash", "-exit", str(script)],
    }


def declarations(plan: dict[str, Any], workspace: Path) -> list[dict[str, Any]]:
    report = workspace / str(plan["report_path"])
    result = []
    if report.is_file():
        result.append({
            "kind": "analysis_report", "path": str(plan["report_path"]),
            "metadata": {"report": plan["report"], "producer": "openroad_report"},
        })
    if (workspace / str(plan["script_path"])).is_file():
        result.append({
            "kind": "analysis_script", "path": str(plan["script_path"]),
            "metadata": {"report": plan["report"], "producer": "openroad_report"},
        })
    result_path = plan.get("result_path")
    if isinstance(result_path, str) and (workspace / result_path).is_file():
        result.append({
            "kind": "analysis_result", "path": result_path,
            "metadata": {"report": plan["report"], "producer": "openroad_report_parser"},
        })
    return result


def normalize(plan: dict[str, Any], workspace: Path) -> None:
    """Write the structured view supported by the official report format."""
    if plan["report"] == "timing":
        return _normalize_timing(plan, workspace)
    if plan["report"] == "area":
        return _normalize_area(plan, workspace)
    if plan["report"] == "power":
        return _normalize_power(plan, workspace)


def _normalize_timing(plan: dict[str, Any], workspace: Path) -> None:
    report_path = workspace / str(plan["report_path"])
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("checks", payload.get("paths"))
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("timing report JSON must contain a checks or paths list")
    pointer_root = ("checks" if isinstance(payload, dict) and "checks" in payload
                    else "paths" if isinstance(payload, dict) else "")
    facts = [
        {
            "record": row,
            "evidence": [{
                "artifact_kind": "analysis_report",
                "logical_path": plan["report_path"],
                "source_type": "json",
                "json_pointer": f"/{pointer_root}/{index}" if pointer_root
                else f"/{index}",
            }],
        }
        for index, row in enumerate(rows) if isinstance(row, dict)
    ]
    metrics: list[dict[str, Any]] = [{
        "name": "timing_path_count", "value": len(facts), "unit": "count",
        "context": {"source_artifact_store_key": plan["report_path"]},
    }]
    slacks = [row["slack"] for row in rows if isinstance(row, dict)
              and isinstance(row.get("slack"), (int, float))]
    if len(slacks) == len(facts) and slacks:
        metrics.append({
            "name": "worst_slack", "value": min(slacks), "unit": "s",
            "context": {"source_artifact_store_key": plan["report_path"]},
        })
    plan["metrics"] = metrics
    result_path = workspace / "analysis_result.json"
    result_path.write_text(json.dumps({
        "schema_version": 1,
        "report": plan["report"],
        "source_report": plan["report_path"],
        "status": "parsed",
        "record_count": len(facts),
        "records": facts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    plan["result_path"] = result_path.relative_to(workspace).as_posix()


def _normalize_area(plan: dict[str, Any], workspace: Path) -> None:
    report_path = workspace / str(plan["report_path"])
    lines = report_path.read_text(encoding="utf-8").splitlines()
    match = next((_AREA_RE.fullmatch(line.strip()) for line in lines), None)
    if match is None:
        raise ValueError("area report does not contain the official design-area line")
    area = float(match.group("area"))
    utilization = float(match.group("utilization"))
    line_number = next(index for index, line in enumerate(lines, 1)
                       if _AREA_RE.fullmatch(line.strip()))
    record = {
        "design_area": area, "area_unit": "um^2",
        "utilization": utilization, "utilization_unit": "%",
    }
    evidence = [{"artifact_kind": "analysis_report",
                 "logical_path": plan["report_path"], "source_type": "text",
                 "line_start": line_number, "line_end": line_number}]
    plan["metrics"] = [
        {"name": "design_area", "value": area, "unit": "um^2",
         "context": {"source_artifact_store_key": plan["report_path"]}},
        {"name": "utilization", "value": utilization, "unit": "%",
         "context": {"source_artifact_store_key": plan["report_path"]}},
    ]
    _write_structured_result(plan, workspace, [{"record": record,
                                                 "evidence": evidence}])


def _normalize_power(plan: dict[str, Any], workspace: Path) -> None:
    report_path = workspace / str(plan["report_path"])
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("power report JSON must contain category objects")
    records: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for category, values in payload.items():
        if not isinstance(category, str) or not isinstance(values, dict):
            raise ValueError("power report JSON categories must be objects")
        record = {"category": category}
        for component in ("internal", "switching", "leakage", "total"):
            value = values.get(component)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"power category {category!r} lacks numeric {component}")
            record[component] = value
            name = ("power_total" if category == "Total" and component == "total"
                    else f"power_{category.lower()}_{component}")
            metrics.append({"name": name, "value": value, "unit": "W",
                            "context": {"source_artifact_store_key": plan["report_path"]}})
        records.append({"record": record, "evidence": [{
            "artifact_kind": "analysis_report", "logical_path": plan["report_path"],
            "source_type": "json", "json_pointer": f"/{_pointer(category)}",
        }]})
    plan["metrics"] = metrics
    _write_structured_result(plan, workspace, records)


def _write_structured_result(plan: dict[str, Any], workspace: Path,
                            records: list[dict[str, Any]]) -> None:
    plan["result_path"] = "analysis_result.json"
    (workspace / plan["result_path"]).write_text(json.dumps({
        "schema_version": 1, "report": plan["report"],
        "source_report": plan["report_path"], "status": "parsed",
        "record_count": len(records), "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


_AREA_RE = re.compile(
    r"Design area (?P<area>[0-9]+(?:\.[0-9]+)?) um\^2 "
    r"(?P<utilization>[0-9]+(?:\.[0-9]+)?)% utilization\."
)


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def receipt(plan: dict[str, Any], *, returncode: int) -> dict[str, Any]:
    return {"adapter": "openroad_report", "report": plan["report"],
            "command": plan["command"], "report_path": plan["report_path"],
            "returncode": returncode}


def _relative(inputs: dict[str, Any], name: str, *, default: str | None = None) -> str:
    value = inputs.get(name, default)
    if not isinstance(value, str) or not value or value.startswith("/") \
            or ".." in Path(value).parts:
        raise ValueError(f"inputs.{name} must be a relative staged path")
    return value


def _script(inputs: dict[str, Any], odb_path: str, report_path: Path,
            command: str) -> str:
    lines = [
        "# Generated by openroad-data/report_adapter.py.",
        f"read_db {_tcl(odb_path)}",
    ]
    lines.extend(timing_commands(inputs, _tcl))
    if inputs.get("report") == "timing":
        extra_lines, extra_options = directed_options(inputs, _tcl)
        lines.extend(extra_lines)
        command += " " + extra_options
    if inputs.get("report") == "native":
        lines.append(command)
        return "\n".join(lines) + "\n"
    lines.extend([
        f"sta::redirect_file_begin {_tcl(str(report_path))}",
        command,
        "sta::redirect_file_end",
    ])
    return "\n".join(lines) + "\n"

# 改动：增加final_eval行
# 已确定original_cp的来源
"""
python3 extract_trajectories.py \
  --logs-dump-root /path/to/result_dump_1/logs_dump \
  --platform asap7 \
  --design aes \
  --output-dir /path/to/qor_dataset \
  --mode major
"""

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Optional


STANDARD_METRICS: "OrderedDict[str, list[str]]" = OrderedDict([
    ("setup_tns_ns", ["timing__setup__tns"]),
    ("setup_wns_ns", ["timing__setup__ws"]),
    ("hold_tns_ns", ["timing__hold__tns"]),
    ("hold_wns_ns", ["timing__hold__ws"]),
    ("fmax_hz", ["timing__fmax"]),
    ("power_internal_w", ["power__internal__total"]),
    ("power_switching_w", ["power__switching__total"]),
    ("power_leakage_w", ["power__leakage__total"]),
    ("power_total_w", ["power__total"]),
    ("die_area_um2", ["design__die_area"]),
    ("core_area_um2", ["design__core_area"]),
    ("instance_area_um2", ["design__instance__area"]),
    ("instance_count", ["design__instance__count"]),
    ("utilization", ["design__instance__utilization"]),
    ("stdcell_area_um2", ["design__instance__area__stdcell"]),
    ("stdcell_count", ["design__instance__count__stdcell"]),
    ("macro_area_um2", ["design__instance__area__macros"]),
    ("macro_count", ["design__instance__count__macros"]),
    ("flow_warning_count", ["flow__warnings__count"]),
    ("flow_error_count", ["flow__errors__count"]),
    (
        "setup_violation_count",
        [
            "timing__setup__violation__count",
            "timing__drv__setup_violation_count",
            "timing__setup__violations",
        ],
    ),
    (
        "hold_violation_count",
        [
            "timing__hold__violation__count",
            "timing__drv__hold_violation_count",
            "timing__hold__violations",
        ],
    ),
    (
        "max_slew_violation_count",
        [
            "timing__drv__max_slew__count",
            "timing__drv__slew_violation_count",
            "timing__max_slew__violation__count",
        ],
    ),
    (
        "max_cap_violation_count",
        [
            "timing__drv__max_cap__count",
            "timing__drv__cap_violation_count",
            "timing__max_capacitance__violation__count",
        ],
    ),
    (
        "max_fanout_violation_count",
        [
            "timing__drv__max_fanout__count",
            "timing__drv__fanout_violation_count",
            "timing__max_fanout__violation__count",
        ],
    ),
    (
        "wirelength_um",
        [
            "route__wirelength",
            "route__wirelength__total",
            "design__wirelength",
            "globalroute__wirelength",
        ],
    ),
    (
        "drc_count",
        [
            "route__drc_errors",
            "route__drc__count",
            "detailedroute__drc__count",
            "finish__drc__count",
        ],
    ),
    (
        "antenna_violation_count",
        [
            "route__antenna__violations",
            "antenna__violations__count",
            "finish__antenna__violations",
        ],
    ),
])

MAJOR_FILE_PATTERNS = [
    re.compile(r"^2_1_.*floorplan.*\.json$", re.IGNORECASE),
    re.compile(r"^3_3_.*place_gp.*\.json$", re.IGNORECASE),
    re.compile(r"^3_4_.*resized.*\.json$", re.IGNORECASE),
    re.compile(r"^3_5_.*place_dp.*\.json$", re.IGNORECASE),
    re.compile(r"^4_1_.*cts.*\.json$", re.IGNORECASE),
    re.compile(r"^5_1_.*grt.*\.json$", re.IGNORECASE),
    re.compile(r"^6_.*report.*\.json$", re.IGNORECASE),
]

FINAL_EVAL_CHECKPOINT = "final_eval"
FLOAT_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def numeric_sort_key(path: Path) -> tuple:
    parts = re.split(r"(\d+)", path.name.lower())
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
        if part != ""
    )


def stage_group_from_filename(filename: str) -> str:
    match = re.match(r"^(\d+)", filename)
    if not match:
        return "unknown"
    return {
        "1": "synthesis",
        "2": "floorplan",
        "3": "placement",
        "4": "cts",
        "5": "routing",
        "6": "finish",
    }.get(match.group(1), f"stage_{match.group(1)}")


def checkpoint_from_filename(filename: str) -> str:
    stem = Path(filename).stem.lower()
    rules = [
        ("synth", "post_synthesis"),
        ("floorplan_macro", "post_macro_placement"),
        ("floorplan_tapcell", "post_tapcell"),
        ("floorplan_pdn", "post_pdn"),
        ("floorplan", "post_floorplan"),
        ("place_gp_skip_io", "global_place_pre_io"),
        ("place_iop", "post_io_placement"),
        ("place_gp", "post_global_placement"),
        ("place_resized", "post_place_resize"),
        ("place_dp", "post_detailed_placement"),
        ("cts", "post_cts"),
        ("grt", "post_global_route"),
        ("route", "post_detailed_route"),
        ("fillcell", "post_fillcell"),
        ("fill", "post_fill"),
        ("report", "final_report"),
    ]
    for token, label in rules:
        if token in stem:
            return label
    return stem


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def find_metric(data: dict[str, Any], candidates: Iterable[str]) -> Any:
    for suffix in candidates:
        ending = "__" + suffix
        matches = [
            (key, value)
            for key, value in data.items()
            if key == suffix or key.endswith(ending)
        ]
        if not matches:
            continue
        scalar_matches = [(key, value) for key, value in matches if is_scalar(value)]
        if scalar_matches:
            return scalar_matches[-1][1]
        return matches[-1][1]
    return None


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Top-level JSON value is not an object: {path}")
    return data


def parse_param_assignment(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise argparse.ArgumentTypeError(
            f"Parameter must use KEY=VALUE syntax: {text!r}"
        )
    key, value = text.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        raise argparse.ArgumentTypeError(f"Empty parameter name: {text!r}")
    return key, value


def parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    match = re.search(FLOAT_RE, str(value).strip())
    if not match:
        return None
    result = float(match.group(0))
    return result if math.isfinite(result) else None


def parse_vars_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    assignment = re.compile(
        r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:?+]?=\s*(.*?)\s*$"
    )
    for raw_line in path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = assignment.match(line)
        if match:
            key, value = match.groups()
            values[key] = value.strip().strip("'\"")
    return values


def read_first_number_file(candidates: Iterable[Path]) -> tuple[Optional[float], Optional[Path]]:
    for path in candidates:
        if not path.is_file():
            continue
        value = parse_number(path.read_text(encoding="utf-8", errors="replace"))
        if value is not None:
            return value, path
    return None, None

def read_original_cp_from_constraint_sdc(
    sdc_path: Path,
) -> Optional[float]:
    """
    从 constraint_N.sdc 中读取：

        set clk_period 0.95

    返回 clk_period:未找到或数值无效时返回 None。
    """
    if not sdc_path.is_file():
        return None

    text = sdc_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    match = re.search(
        rf"^\s*set\s+clk_period\s+({FLOAT_RE})(?:\s|$)",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None

    value = parse_number(match.group(1))
    if value is None or value <= 0:
        return None

    return value

def discover_json_files(run_log_dir: Path, mode: str) -> list[Path]:
    files = sorted(run_log_dir.glob("*.json"), key=numeric_sort_key)
    if mode == "all":
        return files
    major = [
        path
        for path in files
        if any(pattern.match(path.name) for pattern in MAJOR_FILE_PATTERNS)
    ]
    return major if major else files


def infer_run_identity(run_log_dir: Path, work_home: Path) -> tuple[str, str, str]:
    try:
        relative = run_log_dir.resolve().relative_to((work_home / "logs").resolve())
        parts = relative.parts
        if len(parts) >= 3:
            return parts[-3], parts[-2], parts[-1]
    except ValueError:
        pass

    parts = run_log_dir.resolve().parts
    if len(parts) < 3:
        raise ValueError("Cannot infer platform/design/variant from run directory.")
    return parts[-3], parts[-2], parts[-1]


def discover_run_dirs(work_home: Path) -> list[Path]:
    logs_root = work_home / "logs"
    if not logs_root.is_dir():
        return []
    run_dirs = {json_file.parent for json_file in logs_root.glob("*/*/*/*.json")}
    return sorted(run_dirs, key=numeric_sort_key)


def discover_dump_run_dirs(
    logs_dump_root: Path,
) -> list[Path]:
    """
    递归寻找包含 JSON 的 run/base 目录。

    支持：
      logs_dump/base_1/*.json
      logs_dump/aes/run_1/*.json
      logs_dump/design/group/run_1/*.json
    """
    if not logs_dump_root.is_dir():
        return []

    run_dir_pattern = re.compile(
        r"^(?:base|run)_?\d+$",
        re.IGNORECASE,
    )

    candidates = {
        json_path.parent
        for json_path in logs_dump_root.rglob("*.json")
        if run_dir_pattern.match(json_path.parent.name)
    }

    return sorted(
        candidates,
        key=lambda path: numeric_sort_key(path),
    )


def extract_run_number(name: str) -> Optional[int]:
    patterns = [
        r"^(?:base|run)_?(\d+)$",
        r"(?:base|run)_?(\d+)",
        r"(\d+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def discover_eval_log(
    run_log_dir: Path,
    explicit_path: Optional[Path],
    logs_dump_root: Optional[Path] = None,
) -> Optional[Path]:
    if explicit_path is not None:
        return (
            explicit_path
            if explicit_path.is_file()
            else None
        )

    run_number = extract_run_number(
        run_log_dir.name
    )
    if run_number is None:
        return None

    # 优先从命令行提供的 logs_dump 根目录查找。
    # 同时保留 run 直接父目录作为兼容路径。
    search_roots: list[Path] = []

    if logs_dump_root is not None:
        search_roots.append(
            logs_dump_root.expanduser().resolve()
        )

    search_roots.append(
        run_log_dir.parent.resolve()
    )

    # 去掉重复目录，同时保持顺序。
    unique_roots: list[Path] = []
    seen: set[Path] = set()

    for root in search_roots:
        if root not in seen:
            unique_roots.append(root)
            seen.add(root)

    exact_names = [
        f"eval_final_run{run_number}.log",
        f"eval_final_run_{run_number}.log",
        f"eval_tns_final_run{run_number}.log",
        f"eval_tns_final_run_{run_number}.log",
        f"eval_tns_run{run_number}.log",
    ]

    for root in unique_roots:
        for name in exact_names:
            candidate = root / name
            if candidate.is_file():
                return candidate

    # 文件名不完全一致时进行模糊搜索。
    fuzzy_candidates: list[Path] = []

    for root in unique_roots:
        fuzzy_candidates.extend(
            path
            for path in root.glob(
                "*eval*final*run*.log"
            )
            if (
                extract_run_number(path.stem)
                == run_number
                or re.search(
                    rf"run_?{run_number}(?:\D|$)",
                    path.stem,
                    re.IGNORECASE,
                )
            )
        )

    fuzzy_candidates = sorted(
        set(fuzzy_candidates),
        key=numeric_sort_key,
    )

    return (
        fuzzy_candidates[0]
        if fuzzy_candidates
        else None
    )


def last_regex_float(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if matches:
            value = matches[-1]
            if isinstance(value, tuple):
                value = value[-1]
            parsed = parse_number(value)
            if parsed is not None:
                return parsed
    return None


def parse_final_eval_log(path: Path) -> dict[str, Optional[float]]:
    text = path.read_text(encoding="utf-8", errors="replace")

    setup_tns = last_regex_float(
        text,
        [
            rf"\[TNS_EVAL\]\[final\]\s*tns_eval\s*=\s*({FLOAT_RE})",
            rf"^\s*tns\s+({FLOAT_RE})(?:\s|$)",
            rf"\btns\s+max\s+({FLOAT_RE})",
        ],
    )
    setup_wns = last_regex_float(
        text,
        [
            rf"^\s*wns\s+({FLOAT_RE})(?:\s|$)",
            rf"\bwns\s+max\s+({FLOAT_RE})",
        ],
    )
    power_total = last_regex_float(
        text,
        [rf"\[POWER_EVAL\]\[final\]\s*power_eval\s*=\s*({FLOAT_RE})"]
    )

    if power_total is None:
        # OpenROAD report_power 的 Total 行：第 5 列是 total power。
        total_values: list[float] = []
        for line in text.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[0] == "Total":
                parsed = parse_number(fields[4])
                if parsed is not None:
                    total_values.append(parsed)
        if total_values:
            power_total = total_values[-1]

    eval_cp0 = last_regex_float(
        text,
        [
            rf"\bCP_?0\s*=\s*({FLOAT_RE})",
            rf"\bLoaded\s+CP_?0\s*=\s*({FLOAT_RE})",
            rf"\bwith\s+period\s+({FLOAT_RE})",
            rf"\bCreating\s+clock[^\n]*?period\s+({FLOAT_RE})",
            rf"\bclock\s+period\s+to\s+({FLOAT_RE})",
        ],
    )

    return {
        "setup_tns_ns": setup_tns,
        "setup_wns_ns": setup_wns,
        "power_total_w": power_total,
        "eval_cp0": eval_cp0,
    }


def infer_original_cp_from_json(json_files: Iterable[Path]) -> Optional[float]:
    candidate_key = re.compile(
        r"(?:^|__)(?:clock_period|clock__period|timing__clock__period)$",
        re.IGNORECASE,
    )
    for path in json_files:
        try:
            data = read_json(path)
        except Exception:
            continue
        for key, value in data.items():
            if candidate_key.search(str(key)):
                parsed = parse_number(value)
                if parsed is not None and parsed > 0:
                    return parsed
    return None


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extract_one_run(
    run_log_dir: Path,
    work_home: Path,
    output_root: Path,
    mode: str,
    cli_params: dict[str, str],
    platform_override: Optional[str] = None,
    design_override: Optional[str] = None,
    variant_override: Optional[str] = None,
    eval_log_override: Optional[Path] = None,
    eval_cp0_override: Optional[float] = None,
    require_final_eval: bool = True,
    require_cp: bool = True,
    logs_dump_root: Optional[Path] = None,
)-> tuple[list[dict[str, Any]], dict[str, Any]]:
    inferred_platform, inferred_design, inferred_variant = infer_run_identity(
        run_log_dir, work_home
    )

    platform = platform_override or inferred_platform
    design = design_override or inferred_design
    variant = variant_override or inferred_variant
    run_id = f"{platform}__{design}__{variant}"

    results_dir = work_home / "results" / platform / design / variant
    objects_dir = work_home / "objects" / platform / design / variant
    reports_dir = work_home / "reports" / platform / design / variant
    metadata_path = work_home / "run_metadata" / platform / design / f"{variant}.json"

    parameters: dict[str, Any] = {
        "CLOCK_PERIOD": None,
        "CORE_UTILIZATION": None,
        "PLACE_DENSITY_LB_ADDON": None,
    }

    if metadata_path.is_file():
        with metadata_path.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
        parameters.update(
            {
                "CLOCK_PERIOD": meta.get("clock_period_ns"),
                "CORE_UTILIZATION": meta.get("core_utilization"),
                "PLACE_DENSITY_LB_ADDON": meta.get("place_density_lb_addon"),
            }
        )

    parameters.update(cli_params)

    json_files = discover_json_files(run_log_dir, mode)
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {run_log_dir}")

    original_cp = parse_number(parameters.get("CLOCK_PERIOD"))
    original_cp_source: Optional[str] = (
        "metadata/cli"
        if original_cp is not None
        else None
    )

    run_number = (
        extract_run_number(variant)
        or extract_run_number(run_log_dir.name)
    )

    # 历史 dump 中：
    #   logs_dump/base_1  <->  constraint_1.sdc
    #   logs_dump/base_2  <->  constraint_2.sdc
    if original_cp is None and run_number is not None:
        if logs_dump_root is not None:
            constraint_sdc_path = (
                logs_dump_root.parent
                / f"constraint_{run_number}.sdc"
            )
        else:
            # 非 dump 模式下的兼容兜底。
            constraint_sdc_path = (
                run_log_dir.parent.parent
                / f"constraint_{run_number}.sdc"
            )

        original_cp = read_original_cp_from_constraint_sdc(
            constraint_sdc_path
        )

        if original_cp is not None:
            original_cp_source = str(
                constraint_sdc_path
            )

    if original_cp is None:
        cp_file_candidates = [
            results_dir / "clock_period.txt",
            run_log_dir / "clock_period.txt",
            run_log_dir.parent / "clock_period.txt",
        ]

        if run_number is not None:
            cp_file_candidates.extend(
                [
                    run_log_dir.parent
                    / f"clock_period_run{run_number}.txt",

                    run_log_dir.parent.parent
                    / "results_dump"
                    / f"base_{run_number}"
                    / "clock_period.txt",
                ]
            )

        original_cp, cp_path = read_first_number_file(
            cp_file_candidates
        )

        if cp_path is not None:
            original_cp_source = str(cp_path)

    if original_cp is None:
        original_cp = infer_original_cp_from_json(json_files)
        if original_cp is not None:
            original_cp_source = "trajectory_json"

    if original_cp is not None:
        parameters["CLOCK_PERIOD"] = original_cp

    eval_log_path = discover_eval_log(
    run_log_dir=run_log_dir,
    explicit_path=eval_log_override,
    logs_dump_root=logs_dump_root,
)
    eval_values: dict[str, Optional[float]] = {
        "setup_tns_ns": None,
        "setup_wns_ns": None,
        "power_total_w": None,
        "eval_cp0": None,
    }
    if eval_log_path is not None:
        eval_values = parse_final_eval_log(eval_log_path)

    eval_cp0 = parse_number(eval_cp0_override)
    eval_cp0_source: Optional[str] = "cli" if eval_cp0 is not None else None
    if eval_cp0 is None:
        eval_cp0 = eval_values.get("eval_cp0")
        if eval_cp0 is not None:
            eval_cp0_source = str(eval_log_path)

    if eval_cp0 is None:
        cp0_file_candidates = [
            run_log_dir.parent / "cp0.txt",
            run_log_dir.parent.parent / "cp0.txt",
            work_home / "designs" / platform / design / "cp0.txt",
        ]
        eval_cp0, cp0_path = read_first_number_file(cp0_file_candidates)
        if cp0_path is not None:
            eval_cp0_source = str(cp0_path)

    final_eval_complete = all(
        eval_values.get(name) is not None
        for name in ("setup_tns_ns", "power_total_w")
    ) and eval_cp0 is not None

    if require_final_eval and not final_eval_complete:
        raise ValueError(
            "final eval 信息不完整: "
            f"eval_log={eval_log_path}, "
            f"tns={eval_values.get('setup_tns_ns')}, "
            f"power={eval_values.get('power_total_w')}, "
            f"eval_cp0={eval_cp0}"
        )
    if require_cp and (original_cp is None or eval_cp0 is None):
        raise ValueError(
            f"CP 信息不完整: original_cp={original_cp}, eval_cp0={eval_cp0}"
        )
    if original_cp is not None and original_cp <= 0:
        raise ValueError(f"original_cp 必须为正数，当前为 {original_cp}")
    if eval_cp0 is not None and eval_cp0 <= 0:
        raise ValueError(f"eval_cp0 必须为正数，当前为 {eval_cp0}")

    parameters_json = json.dumps(parameters, ensure_ascii=False, sort_keys=True)
    trajectory_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []

    for step, json_path in enumerate(json_files):
        try:
            data = read_json(json_path)
            read_error = None
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            data = {}
            read_error = str(exc)

        row: dict[str, Any] = {
            "run_id": run_id,
            "platform": platform,
            "design": design,
            "variant": variant,
            "step": step,
            "stage_group": stage_group_from_filename(json_path.name),
            "checkpoint": checkpoint_from_filename(json_path.name),
            "source_file": json_path.name,
            "json_read_error": read_error,
            "original_cp": original_cp,
            "eval_cp0": eval_cp0,
            "parameters_json": parameters_json,
        }
        for column, suffixes in STANDARD_METRICS.items():
            row[column] = find_metric(data, suffixes)
        trajectory_rows.append(row)

        for key, value in sorted(data.items()):
            if not is_scalar(value):
                continue
            raw_rows.append(
                {
                    "run_id": run_id,
                    "platform": platform,
                    "design": design,
                    "variant": variant,
                    "step": step,
                    "stage_group": row["stage_group"],
                    "checkpoint": row["checkpoint"],
                    "source_file": json_path.name,
                    "metric_key": key,
                    "metric_value": value,
                    "value_type": type(value).__name__,
                }
            )

    if eval_log_path is not None or final_eval_complete:
        final_row: dict[str, Any] = {
            "run_id": run_id,
            "platform": platform,
            "design": design,
            "variant": variant,
            "step": len(trajectory_rows),
            "stage_group": "evaluation",
            "checkpoint": FINAL_EVAL_CHECKPOINT,
            "source_file": eval_log_path.name if eval_log_path else "",
            "json_read_error": None if final_eval_complete else "final_eval_incomplete",
            "original_cp": original_cp,
            "eval_cp0": eval_cp0,
            "parameters_json": parameters_json,
        }
        for column in STANDARD_METRICS:
            final_row[column] = None
        final_row["setup_tns_ns"] = eval_values.get("setup_tns_ns")
        final_row["setup_wns_ns"] = eval_values.get("setup_wns_ns")
        final_row["power_total_w"] = eval_values.get("power_total_w")
        trajectory_rows.append(final_row)

    run_output_dir = output_root / platform / design / variant
    trajectory_columns = [
        "run_id",
        "platform",
        "design",
        "variant",
        "step",
        "stage_group",
        "checkpoint",
        "source_file",
        "json_read_error",
        "original_cp",
        "eval_cp0",
        *STANDARD_METRICS.keys(),
        "parameters_json",
    ]
    raw_columns = [
        "run_id",
        "platform",
        "design",
        "variant",
        "step",
        "stage_group",
        "checkpoint",
        "source_file",
        "metric_key",
        "metric_value",
        "value_type",
    ]
    write_csv(run_output_dir / "trajectory.csv", trajectory_rows, trajectory_columns)
    write_csv(run_output_dir / "raw_metrics_long.csv", raw_rows, raw_columns)

    metadata: dict[str, Any] = {
        "run_id": run_id,
        "platform": platform,
        "design": design,
        "variant": variant,
        "work_home": str(work_home),
        "logs_dir": str(run_log_dir),
        "reports_dir": str(reports_dir),
        "results_dir": str(results_dir),
        "objects_dir": str(objects_dir),
        "json_mode": mode,
        "native_checkpoint_count": len(json_files),
        "checkpoint_count": len(trajectory_rows),
        "parameters": parameters,
        "original_cp": original_cp,
        "original_cp_source": original_cp_source,
        "eval_cp0": eval_cp0,
        "eval_cp0_source": eval_cp0_source,
        "final_eval_log": str(eval_log_path) if eval_log_path else None,
        "final_eval_complete": final_eval_complete,
        "final_eval": {
            "setup_tns_ns": eval_values.get("setup_tns_ns"),
            "setup_wns_ns": eval_values.get("setup_wns_ns"),
            "power_total_w": eval_values.get("power_total_w"),
        },
    }
    run_output_dir.mkdir(parents=True, exist_ok=True)
    (run_output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return trajectory_rows, metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract ORFS QoR trajectories and append one final_eval row from "
            "the fixed-CP0 re-evaluation log."
        )
    )
    parser.add_argument("--work-home", default="~/orfs_work")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--mode", choices=["all", "major"], default="major")

    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all-runs", action="store_true")
    scope.add_argument("--run-dir")
    scope.add_argument("--single-run", action="store_true")
    scope.add_argument(
        "--logs-dump-root",
        help=(
            "历史 dump 的 logs_dump 目录，例如 "
            "result_dump_1/logs_dump;会扫描其 base_* 子目录"
        ),
    )

    parser.add_argument("--platform")
    parser.add_argument("--design")
    parser.add_argument("--variant", default=None)
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument(
        "--eval-log",
        type=Path,
        default=None,
        help="仅单 run 时显式指定 eval_final_runN.log",
    )
    parser.add_argument(
        "--eval-cp0",
        type=float,
        default=None,
        help="显式覆盖本次提取的统一评价 CP0",
    )
    parser.add_argument(
        "--allow-missing-final-eval",
        action="store_true",
        help="允许缺少 final_eval；默认缺失会令该 run 提取失败",
    )
    parser.add_argument(
        "--allow-missing-cp",
        action="store_true",
        help="允许 original_cp/eval_cp0 缺失；默认缺失会令该 run 提取失败",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    work_home = expand_path(args.work_home)
    output_root = (
        expand_path(args.output_dir) if args.output_dir else work_home / "qor_dataset"
    )

    cli_params: dict[str, str] = {}
    for item in args.param:
        key, value = parse_param_assignment(item)
        cli_params[key] = value

    dump_mode = args.logs_dump_root is not None
    logs_dump_root: Optional[Path] = None

    if dump_mode:
        if not args.platform or not args.design:
            parser.error("--logs-dump-root requires --platform and --design")

        logs_dump_root = expand_path(args.logs_dump_root)

        run_dirs = discover_dump_run_dirs(logs_dump_root)

        if not run_dirs:
            parser.error(
                f"No JSON run directories found under "
                f"{logs_dump_root}"
            )

    elif args.all_runs:
        run_dirs = discover_run_dirs(work_home)
        if not run_dirs:
            parser.error(f"No ORFS JSON runs found under {work_home / 'logs'}")
    elif args.run_dir:
        run_dirs = [expand_path(args.run_dir)]
    else:
        if not args.platform or not args.design or not args.variant:
            parser.error(
                "--single-run requires --platform, --design and --variant"
            )
        run_dirs = [work_home / "logs" / args.platform / args.design / args.variant]

    all_trajectory_rows: list[dict[str, Any]] = []
    all_metadata: list[dict[str, Any]] = []
    failures = 0

    for run_dir in run_dirs:
        try:
            per_run_variant = (
                args.variant
                if len(run_dirs) == 1 and args.variant is not None
                else run_dir.name
            )
            trajectory_rows, metadata = extract_one_run(
                run_log_dir=run_dir,
                work_home=work_home,
                output_root=output_root,
                mode=args.mode,
                cli_params=cli_params,
                platform_override=args.platform,
                design_override=args.design,
                variant_override=per_run_variant if dump_mode else args.variant,
                eval_log_override=(
                    expand_path(args.eval_log)
                    if args.eval_log is not None and len(run_dirs) == 1
                    else None
                ),
                eval_cp0_override=args.eval_cp0,
                require_final_eval=not args.allow_missing_final_eval,
                require_cp=not args.allow_missing_cp,
                logs_dump_root=logs_dump_root,
            )
        except Exception as exc:
            failures += 1
            print(f"[ERROR] {run_dir}: {exc}", file=sys.stderr)
            continue

        all_trajectory_rows.extend(trajectory_rows)
        all_metadata.append(metadata)
        print(
            f"[OK] {metadata['run_id']}: "
            f"native={metadata['native_checkpoint_count']}, "
            f"final_eval={metadata['final_eval_complete']}, "
            f"original_cp={metadata['original_cp']}, "
            f"eval_cp0={metadata['eval_cp0']}"
        )

    if all_trajectory_rows:
        trajectory_columns = [
            "run_id",
            "platform",
            "design",
            "variant",
            "step",
            "stage_group",
            "checkpoint",
            "source_file",
            "json_read_error",
            "original_cp",
            "eval_cp0",
            *STANDARD_METRICS.keys(),
            "parameters_json",
        ]
        write_csv(output_root / "trajectory_all.csv", all_trajectory_rows, trajectory_columns)

    if all_metadata:
        metadata_rows: list[dict[str, Any]] = []
        for metadata in all_metadata:
            parameters = metadata.get("parameters", {})
            final_eval = metadata.get("final_eval", {})
            metadata_rows.append(
                {
                    "run_id": metadata["run_id"],
                    "platform": metadata["platform"],
                    "design": metadata["design"],
                    "variant": metadata["variant"],
                    "native_checkpoint_count": metadata["native_checkpoint_count"],
                    "checkpoint_count": metadata["checkpoint_count"],
                    "original_cp": metadata["original_cp"],
                    "eval_cp0": metadata["eval_cp0"],
                    "final_eval_tns": final_eval.get("setup_tns_ns"),
                    "final_eval_power": final_eval.get("power_total_w"),
                    "final_eval_complete": metadata["final_eval_complete"],
                    "parameters_json": json.dumps(
                        parameters, ensure_ascii=False, sort_keys=True
                    ),
                    "logs_dir": metadata["logs_dir"],
                    "reports_dir": metadata["reports_dir"],
                    "results_dir": metadata["results_dir"],
                    "final_eval_log": metadata["final_eval_log"],
                }
            )
        write_csv(
            output_root / "runs_metadata.csv",
            metadata_rows,
            [
                "run_id",
                "platform",
                "design",
                "variant",
                "native_checkpoint_count",
                "checkpoint_count",
                "original_cp",
                "eval_cp0",
                "final_eval_tns",
                "final_eval_power",
                "final_eval_complete",
                "parameters_json",
                "logs_dir",
                "reports_dir",
                "results_dir",
                "final_eval_log",
            ],
        )

    print(f"\nDataset output: {output_root}")
    print(f"Runs succeeded: {len(all_metadata)}")
    print(f"Runs failed:    {failures}")
    return 1 if failures and not all_metadata else 0


if __name__ == "__main__":
    raise SystemExit(main())

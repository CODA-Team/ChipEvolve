# 改动：增加记录该run的original_cp、eval_cp0、final_tns和final_power 
"""
python3 build_run_manifest.py \
  --roots \
    /path/qor_dataset_1 \
    /path/qor_dataset_2 \
    /path/qor_dataset_3 \
  --output /path/run_manifest.csv \
  --relative-paths \
  --overwrite \
  --train-ratio 0.7 \
  --val-ratio 0.15 \
  --test-ratio 0.15
"""

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


FINAL_EVAL_CHECKPOINT = "final_eval"
IGNORE_COLUMNS_FOR_HASH = {
    "run_id",
    "platform",
    "design",
    "variant",
    "parameters_json",
    "json_read_error",
}


@dataclass
class RunRecord:
    run_id: str
    trajectory_path: Path
    platform: str
    design: str
    variant: str
    original_variant: str
    source_dataset: str
    native_row_count: int
    total_row_count: int
    final_eval_count: int
    original_cp: float
    eval_cp0: float
    final_eval_tns: Optional[float]
    final_eval_power: Optional[float]
    trajectory_hash: str
    split: str = ""


def natural_key(value: str):
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part for part in parts)


def norm_cell(value: str | None) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in {"nan", "none", "null"}:
        return ""
    return value


def parse_finite_float(value: object) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def inspect_trajectory(csv_path: Path) -> dict[str, object]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"empty csv: {csv_path}")
        if "checkpoint" not in reader.fieldnames:
            raise ValueError(f"trajectory 缺少 checkpoint 列: {csv_path}")

        rows = [row for row in reader if any(norm_cell(cell) for cell in row.values())]

    final_rows = [
        row
        for row in rows
        if norm_cell(row.get("checkpoint")) == FINAL_EVAL_CHECKPOINT
    ]
    native_rows = [
        row
        for row in rows
        if norm_cell(row.get("checkpoint")) != FINAL_EVAL_CHECKPOINT
    ]

    original_cp = None
    eval_cp0 = None
    for row in rows:
        if original_cp is None:
            original_cp = parse_finite_float(row.get("original_cp"))
        if eval_cp0 is None:
            eval_cp0 = parse_finite_float(row.get("eval_cp0"))

    final_eval_tns = None
    final_eval_power = None
    if final_rows:
        final_eval_tns = parse_finite_float(final_rows[-1].get("setup_tns_ns"))
        final_eval_power = parse_finite_float(final_rows[-1].get("power_total_w"))

    return {
        "native_row_count": len(native_rows),
        "total_row_count": len(rows),
        "final_eval_count": len(final_rows),
        "original_cp": original_cp,
        "eval_cp0": eval_cp0,
        "final_eval_tns": final_eval_tns,
        "final_eval_power": final_eval_power,
    }


def trajectory_hash(csv_path: Path, ignore_source_file: bool) -> str:
    h = hashlib.sha256()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"empty csv: {csv_path}")

        ignore = set(IGNORE_COLUMNS_FOR_HASH)
        if ignore_source_file:
            ignore.add("source_file")
        columns = [column for column in reader.fieldnames if column not in ignore]

        h.update(("COLUMNS\t" + "\t".join(columns) + "\n").encode("utf-8"))
        for row in reader:
            values = [norm_cell(row.get(column)) for column in columns]
            h.update(("ROW\t" + "\t".join(values) + "\n").encode("utf-8"))
    return h.hexdigest()


def infer_identity(root: Path, trajectory_path: Path) -> tuple[str, str, str]:
    rel = trajectory_path.resolve().relative_to(root.resolve())
    parts = rel.parts
    if len(parts) < 4:
        raise ValueError(
            "路径层级不足，期望 root/platform/design/variant/trajectory.csv: "
            f"{trajectory_path}"
        )
    platform = parts[0]
    design = parts[1]
    variant = "__".join(parts[2:-1])
    return platform, design, variant


def sanitize_token(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"[^A-Za-z0-9_.+-]+", "_", text)
    return text.strip("_") or "unknown"


def load_sidecar_metadata(trajectory_path: Path) -> dict:
    metadata_path = trajectory_path.with_name("metadata.json")
    if not metadata_path.is_file():
        return {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def resolve_cp_and_eval(
    inspection: dict[str, object],
    metadata: dict,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    parameters = metadata.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    original_cp = parse_finite_float(metadata.get("original_cp"))
    if original_cp is None:
        original_cp = parse_finite_float(parameters.get("CLOCK_PERIOD"))
    if original_cp is None:
        original_cp = inspection["original_cp"]  # type: ignore[assignment]

    eval_cp0 = parse_finite_float(metadata.get("eval_cp0"))
    if eval_cp0 is None:
        eval_cp0 = inspection["eval_cp0"]  # type: ignore[assignment]

    final_eval = metadata.get("final_eval", {})
    if not isinstance(final_eval, dict):
        final_eval = {}
    final_eval_tns = parse_finite_float(final_eval.get("setup_tns_ns"))
    if final_eval_tns is None:
        final_eval_tns = inspection["final_eval_tns"]  # type: ignore[assignment]

    final_eval_power = parse_finite_float(final_eval.get("power_total_w"))
    if final_eval_power is None:
        final_eval_power = inspection["final_eval_power"]  # type: ignore[assignment]

    return original_cp, eval_cp0, final_eval_tns, final_eval_power


def collect_runs(
    roots: Iterable[Path],
    trajectory_filename: str,
    expected_native_rows: int,
    min_native_rows: int,
    dedupe_by_hash: bool,
    ignore_source_file: bool,
    require_final_eval: bool,
    require_cp: bool,
) -> tuple[list[RunRecord], list[tuple[str, str]]]:
    runs: list[RunRecord] = []
    skipped: list[tuple[str, str]] = []
    seen_hash: dict[tuple[str, str, str], Path] = {}

    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            skipped.append((str(root), "root doesn't exist"))
            continue

        source_dataset = sanitize_token(f"{root.parent.name}__{root.name}")
        trajectories = sorted(
            root.rglob(trajectory_filename), key=lambda path: natural_key(str(path))
        )

        for trajectory in trajectories:
            if any(part.startswith("_duplicate") for part in trajectory.parts):
                continue

            try:
                platform, design, original_variant = infer_identity(root, trajectory)
                inspection = inspect_trajectory(trajectory)
                metadata = load_sidecar_metadata(trajectory)
                original_cp, eval_cp0, final_tns, final_power = resolve_cp_and_eval(
                    inspection, metadata
                )
            except Exception as exc:
                skipped.append((str(trajectory), f"inspect failed: {exc}"))
                continue

            native_count = int(inspection["native_row_count"])
            total_count = int(inspection["total_row_count"])
            final_eval_count = int(inspection["final_eval_count"])

            if expected_native_rows > 0 and native_count != expected_native_rows:
                skipped.append(
                    (
                        str(trajectory),
                        f"native row count={native_count}, expected={expected_native_rows}",
                    )
                )
                continue
            if min_native_rows > 0 and native_count < min_native_rows:
                skipped.append(
                    (
                        str(trajectory),
                        f"native row count={native_count}, min={min_native_rows}",
                    )
                )
                continue
            if require_final_eval and final_eval_count != 1:
                skipped.append(
                    (
                        str(trajectory),
                        f"final_eval count={final_eval_count}, expected exactly 1",
                    )
                )
                continue
            if require_final_eval and (final_tns is None or final_power is None):
                skipped.append(
                    (
                        str(trajectory),
                        f"final_eval target missing: tns={final_tns}, power={final_power}",
                    )
                )
                continue
            if require_cp and (
                original_cp is None
                or eval_cp0 is None
                or original_cp <= 0
                or eval_cp0 <= 0
            ):
                skipped.append(
                    (
                        str(trajectory),
                        f"invalid CP: original_cp={original_cp}, eval_cp0={eval_cp0}",
                    )
                )
                continue

            try:
                digest = trajectory_hash(
                    trajectory, ignore_source_file=ignore_source_file
                )
            except Exception as exc:
                skipped.append((str(trajectory), f"hash failed: {exc}"))
                continue

            dedupe_key = (platform, design, digest)
            if dedupe_by_hash and dedupe_key in seen_hash:
                skipped.append(
                    (
                        str(trajectory),
                        f"duplicate trajectory, kept: {seen_hash[dedupe_key]}",
                    )
                )
                continue
            seen_hash[dedupe_key] = trajectory

            unique_variant = (
                f"{source_dataset}__{sanitize_token(original_variant)}"
            )
            platform = sanitize_token(platform)
            design = sanitize_token(design)
            run_id = f"{platform}__{design}__{unique_variant}"

            runs.append(
                RunRecord(
                    run_id=run_id,
                    trajectory_path=trajectory.resolve(),
                    platform=platform,
                    design=design,
                    variant=unique_variant,
                    original_variant=original_variant,
                    source_dataset=source_dataset,
                    native_row_count=native_count,
                    total_row_count=total_count,
                    final_eval_count=final_eval_count,
                    original_cp=float(original_cp) if original_cp is not None else math.nan,
                    eval_cp0=float(eval_cp0) if eval_cp0 is not None else math.nan,
                    final_eval_tns=final_tns,
                    final_eval_power=final_power,
                    trajectory_hash=digest,
                )
            )

    return runs, skipped


def ratio_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    if total <= 0:
        return {name: 0 for name in ratios}
    ratio_sum = sum(ratios.values())
    if ratio_sum <= 0:
        raise ValueError("split ratios sum must be positive")

    normalized = {name: value / ratio_sum for name, value in ratios.items()}
    raw = {name: total * value for name, value in normalized.items()}
    counts = {name: math.floor(value) for name, value in raw.items()}
    remain = total - sum(counts.values())
    order = sorted(
        ratios,
        key=lambda name: raw[name] - counts[name],
        reverse=True,
    )
    for name in order[:remain]:
        counts[name] += 1
    return counts


def assign_random_splits(
    runs: list[RunRecord],
    seed: int,
    ratios: dict[str, float],
    split_scope: str,
) -> dict[str, dict[str, int]]:
    """
    只做带 seed 的随机划分，不按 CLOCK_PERIOD/利用率/密度等参数分层。

    默认按 platform/design 分组后分别随机划分，避免不同设计的小组在某个
    split 中完全消失；若指定 global,则所有 run 一起随机划分。
    """
    groups: dict[str, list[RunRecord]] = defaultdict(list)
    if split_scope == "global":
        groups["__global__"] = list(runs)
    else:
        for run in runs:
            groups[f"{run.platform}/{run.design}"].append(run)

    rng = random.Random(seed)
    summary: dict[str, dict[str, int]] = {}
    split_order = tuple(ratios.keys())

    for group_name, group_runs in sorted(groups.items()):
        group_runs.sort(key=lambda run: natural_key(run.run_id))
        rng.shuffle(group_runs)
        counts = ratio_counts(len(group_runs), ratios)
        summary[group_name] = counts

        cursor = 0
        for split in split_order:
            count = counts[split]
            for run in group_runs[cursor : cursor + count]:
                run.split = split
            cursor += count

    return summary


def write_manifest(runs: list[RunRecord], output: Path, relative_paths: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "run_id",
        "trajectory_path",
        "platform",
        "design",
        "variant",
        "original_variant",
        "source_dataset",
        "split",
        "original_cp",
        "eval_cp0",
        "final_eval_tns",
        "final_eval_power",
        "native_row_count",
        "total_row_count",
        "trajectory_hash",
    ]

    split_order = {"train": 0, "val": 1, "test": 2}
    sorted_runs = sorted(
        runs,
        key=lambda run: (
            run.platform,
            run.design,
            split_order.get(run.split, 99),
            natural_key(run.variant),
        ),
    )

    seen_run_ids: set[str] = set()
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for run in sorted_runs:
            if run.run_id in seen_run_ids:
                raise ValueError(f"run_id 重复: {run.run_id}")
            seen_run_ids.add(run.run_id)

            trajectory_path = (
                os.path.relpath(run.trajectory_path, output.parent.resolve())
                if relative_paths
                else str(run.trajectory_path)
            )
            writer.writerow(
                {
                    "run_id": run.run_id,
                    "trajectory_path": trajectory_path,
                    "platform": run.platform,
                    "design": run.design,
                    "variant": run.variant,
                    "original_variant": run.original_variant,
                    "source_dataset": run.source_dataset,
                    "split": run.split,
                    "original_cp": run.original_cp,
                    "eval_cp0": run.eval_cp0,
                    "final_eval_tns": run.final_eval_tns,
                    "final_eval_power": run.final_eval_power,
                    "native_row_count": run.native_row_count,
                    "total_row_count": run.total_row_count,
                    "trajectory_hash": run.trajectory_hash,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build run_manifest.csv from extracted trajectory directories. "
            "Splits are assigned randomly at run level."
        )
    )
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trajectory-filename", default="trajectory.csv")
    parser.add_argument(
        "--expected-native-rows",
        type=int,
        default=7,
        help="只统计 final_eval 之外的原生检查点；0 表示不检查 exact count",
    )
    parser.add_argument("--min-native-rows", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument(
        "--split-scope",
        choices=["platform-design", "global"],
        default="platform-design",
        help="均为纯随机划分；默认在每个 platform/design 内分别随机",
    )
    parser.add_argument("--no-dedupe", action="store_true")
    parser.add_argument("--ignore-source-file", action="store_true")
    parser.add_argument("--allow-missing-final-eval", action="store_true")
    parser.add_argument("--allow-missing-cp", action="store_true")
    parser.add_argument("--relative-paths", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"{output} already exists; use --overwrite")

    ratios = {
        "train": args.train_ratio,
        "val": args.val_ratio,
        "test": args.test_ratio,
    }
    if any(value < 0 for value in ratios.values()) or sum(ratios.values()) <= 0:
        raise ValueError(f"invalid split ratios: {ratios}")

    runs, skipped = collect_runs(
        roots=args.roots,
        trajectory_filename=args.trajectory_filename,
        expected_native_rows=args.expected_native_rows,
        min_native_rows=args.min_native_rows,
        dedupe_by_hash=not args.no_dedupe,
        ignore_source_file=args.ignore_source_file,
        require_final_eval=not args.allow_missing_final_eval,
        require_cp=not args.allow_missing_cp,
    )
    if not runs:
        raise RuntimeError("no usable trajectory.csv found")

    split_summary = assign_random_splits(
        runs=runs,
        seed=args.seed,
        ratios=ratios,
        split_scope=args.split_scope,
    )
    write_manifest(runs, output, args.relative_paths)

    print("\nScan summary")
    print("------------")
    print(f"usable trajectories: {len(runs)}")
    print(f"skipped trajectories: {len(skipped)}")
    print(f"output file: {output}")
    print("\nRandom split summary")
    print("--------------------")
    for group, counts in split_summary.items():
        print(
            f"{group}: total={sum(counts.values())}, "
            f"train={counts['train']}, val={counts['val']}, test={counts['test']}"
        )

    if skipped:
        skipped_path = output.with_suffix(".skipped.csv")
        with skipped_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["path", "reason"])
            writer.writerows(skipped)
        print(f"\nskipped details: {skipped_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

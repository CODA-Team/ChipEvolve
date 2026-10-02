# 改动：现在只允许platform、design、split和 eval_cp0 全部相同的 run 成 pair：
# 允许baseline.original_cp != ongoing.original_cp
# pair_manifest 会额外写入 baseline_original_cp、ongoing_original_cp、eval_cp0、baseline_clock_ratio和ongoing_clock_ratio
"""
python3 build_pairs.py \
  --run-manifest /path/run_manifest.csv \
  --output /path/pair_manifest.csv \
  --shuffle-output
"""

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import random
from itertools import permutations
from pathlib import Path
from typing import Any

import pandas as pd


def require_positive_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    bad = ~values.map(lambda value: math.isfinite(value) and value > 0)
    if bad.any():
        examples = frame.loc[bad, ["run_id", column]].head(10).to_dict("records")
        raise ValueError(f"{column} unusable value: {examples}")
    return values.astype(float)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "从 run_manifest.csv 构造有向 baseline-ongoing pair。"
            "run 的 train/val/test 已在 manifest 中随机划分；"
            "这里只在相同 platform/design/split/eval_cp0 内配对。"
        )
    )
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--eval-cp0-decimals",
        type=int,
        default=6,
        help="用于抵抗 CSV 浮点微小误差；默认按 6 位小数视为同一 CP0",
    )
    parser.add_argument(
        "--max-pairs-per-group",
        type=int,
        default=0,
        help="0 表示保留全部 N*(N-1) 个有向 pair",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--shuffle-output",
        action="store_true",
        help="生成后按 seed 随机打乱 pair 行顺序",
    )
    args = parser.parse_args()

    frame = pd.read_csv(args.run_manifest)
    required = {
        "run_id",
        "platform",
        "design",
        "split",
        "original_cp",
        "eval_cp0",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"run manifest lack columns: {sorted(missing)}")
    if frame["run_id"].astype(str).duplicated().any():
        duplicated = frame.loc[
            frame["run_id"].astype(str).duplicated(), "run_id"
        ].tolist()
        raise ValueError(f"run_id duplicate: {duplicated[:10]}")

    frame = frame.copy()
    frame["run_id"] = frame["run_id"].astype(str)
    frame["original_cp"] = require_positive_numeric(frame, "original_cp")
    frame["eval_cp0"] = require_positive_numeric(frame, "eval_cp0")
    frame["__eval_cp0_group"] = frame["eval_cp0"].round(
        args.eval_cp0_decimals
    )

    group_columns = ["platform", "design", "split", "__eval_cp0_group"]
    output_rows: list[dict[str, Any]] = []
    rng = random.Random(args.seed)

    for group_values, group in frame.groupby(group_columns, dropna=False, sort=True):
        platform, design, split, eval_cp0_group = group_values
        records = group[
            ["run_id", "original_cp", "eval_cp0"]
        ].to_dict(orient="records")
        if len(records) < 2:
            continue

        group_pairs = list(permutations(records, 2))
        if (
            args.max_pairs_per_group > 0
            and len(group_pairs) > args.max_pairs_per_group
        ):
            group_pairs = rng.sample(group_pairs, args.max_pairs_per_group)

        for baseline, ongoing in group_pairs:
            # 二者在同一 round 后的 eval_cp0 可能只有浮点末位差异；
            # pair 中写入量化后的统一值，ratio 也以这个值计算。
            common_cp0 = float(eval_cp0_group)
            output_rows.append(
                {
                    "baseline_run_id": baseline["run_id"],
                    "ongoing_run_id": ongoing["run_id"],
                    "platform": platform,
                    "design": design,
                    "split": split,
                    "eval_cp0": common_cp0,
                    "baseline_original_cp": float(baseline["original_cp"]),
                    "ongoing_original_cp": float(ongoing["original_cp"]),
                    "baseline_clock_ratio": float(baseline["original_cp"])
                    / common_cp0,
                    "ongoing_clock_ratio": float(ongoing["original_cp"])
                    / common_cp0,
                }
            )

    if not output_rows:
        raise RuntimeError(
            "没有生成任何 pair,请检查每个 platform/design/split/eval_cp0 组是否至少有 2 条 run"
        )

    if args.shuffle_output:
        rng.shuffle(output_rows)

    output = pd.DataFrame(output_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)

    print(f"written {len(output)} pairs -> {args.output}")
    summary = (
        output.groupby(["platform", "design", "split", "eval_cp0"])
        .size()
        .reset_index(name="pair_count")
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

"""
扫描多个 qor_dataset,计算每个 trajectory.csv 的“规范化 hash”,
找出完全重复的轨迹，只保留一个，其余移动到重复目录。

python3 dedup_trajectories.py \
  /path/to/qor_dataset_1 \
  /path/to/qor_dataset_2 \
  --report /path/to/duplicate_trajectory_report.csv \
  --action check \
  --duplicate-dir /path/to/duplicate_trajectories_removed
"""
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


# 这些列只表示身份/来源，不参与“轨迹是否相同”的判断
DEFAULT_IGNORE_COLUMNS = {
    "run_id",
    "platform",
    "design",
    "variant",
    "parameters_json",
    "json_read_error",
}


def norm_cell(value: str | None) -> str:
    """
    统一空值格式，避免 None、空字符串、nan 这种表现差异影响 hash。
    """
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in {"nan", "none", "null"}:
        return ""
    return value


def natural_key(path: Path):
    """
    简单自然排序，让 result_dump_2 排在 result_dump_10 前面。
    """
    import re

    parts = re.split(r"(\d+)", str(path))
    return tuple(int(p) if p.isdigit() else p for p in parts)


def trajectory_hash(
    trajectory_csv: Path,
    ignore_columns: set[str],
    keep_source_file: bool,
) -> tuple[str, int, list[str]]:
    """
    对 trajectory.csv 做规范化 hash。

    默认忽略 run_id/platform/design/variant 等身份列。
    默认保留 source_file，因为它有助于保证 checkpoint 序列完全一致。
    如果不同数据集的 source_file 文件名也可能不同，但指标轨迹一样，
    可以运行时加 --ignore-source-file。
    """
    h = hashlib.sha256()
    row_count = 0

    with trajectory_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"empty or invalid csv: {trajectory_csv}")

        ignore = set(ignore_columns)
        if not keep_source_file:
            ignore.add("source_file")

        columns = [c for c in reader.fieldnames if c not in ignore]

        # 关键：固定列顺序，先写入列名
        h.update(("COLUMNS\t" + "\t".join(columns) + "\n").encode("utf-8"))

        for row in reader:
            row_count += 1
            values = [norm_cell(row.get(c)) for c in columns]
            h.update(("ROW\t" + "\t".join(values) + "\n").encode("utf-8"))

    return h.hexdigest(), row_count, columns


def find_run_dir_from_trajectory(traj: Path) -> Path:
    """
    trajectory.csv 所在目录就是一个 run 的输出目录：
    qor_dataset/asap7/aes/<variant>/trajectory.csv
    """
    return traj.parent


def safe_move_dir(src: Path, dst: Path) -> Path:
    """
    安全移动目录。如果目标已存在，自动加后缀。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)

    final_dst = dst
    idx = 1
    while final_dst.exists():
        final_dst = dst.with_name(f"{dst.name}__dup{idx}")
        idx += 1

    shutil.move(str(src), str(final_dst))
    return final_dst


def collect_trajectory_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"[WARN] root not exists: {root}", file=sys.stderr)
            continue
        files.extend(root.rglob("trajectory.csv"))

    return sorted(files, key=natural_key)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and remove duplicate QoR trajectory.csv files efficiently."
    )
    parser.add_argument(
        "roots",
        nargs="+",
        help="qor_dataset roots, e.g. /path/to/qor_dataset_1",
    )
    parser.add_argument(
        "--report",
        default="duplicate_trajectory_report.csv",
        help="output duplicate report csv",
    )
    parser.add_argument(
        "--action",
        choices=["check", "move", "delete"],
        default="check",
        help="check: only report; move: move duplicate run dirs; delete: delete duplicate run dirs",
    )
    parser.add_argument(
        "--duplicate-dir",
        default=None,
        help="where to move duplicate run dirs when --action move. Default: <first_root>/_duplicate_trajectories",
    )
    parser.add_argument(
        "--ignore-source-file",
        action="store_true",
        help="ignore source_file column too. Use this if same checkpoints have different json filenames.",
    )
    parser.add_argument(
        "--prefer-root",
        default=None,
        help="prefer keeping trajectories under this root if duplicates exist.",
    )
    args = parser.parse_args()

    roots = [Path(p).expanduser().resolve() for p in args.roots]
    report_path = Path(args.report).expanduser().resolve()

    duplicate_dir = (
        Path(args.duplicate_dir).expanduser().resolve()
        if args.duplicate_dir
        else roots[0] / "_duplicate_trajectories"
    )

    prefer_root = Path(args.prefer_root).expanduser().resolve() if args.prefer_root else None

    traj_files = collect_trajectory_files(roots)

    print(f"[INFO] found trajectory.csv files: {len(traj_files)}")

    if not traj_files:
        print("[ERROR] no trajectory.csv found")
        return 1

    groups: dict[str, list[dict]] = defaultdict(list)
    errors = []

    for i, traj in enumerate(traj_files, start=1):
        if i % 500 == 0:
            print(f"[INFO] hashed {i}/{len(traj_files)}")

        try:
            digest, row_count, used_columns = trajectory_hash(
                traj,
                ignore_columns=DEFAULT_IGNORE_COLUMNS,
                keep_source_file=not args.ignore_source_file,
            )
        except Exception as exc:
            errors.append((traj, str(exc)))
            continue

        groups[digest].append(
            {
                "trajectory_csv": traj,
                "run_dir": find_run_dir_from_trajectory(traj),
                "row_count": row_count,
                "used_columns": used_columns,
            }
        )

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    print(f"[INFO] unique trajectory hashes: {len(groups)}")
    print(f"[INFO] duplicate groups: {len(duplicate_groups)}")
    print(
        f"[INFO] duplicate trajectories to remove: "
        f"{sum(len(v) - 1 for v in duplicate_groups.values())}"
    )

    report_rows = []

    def keep_sort_key(item: dict):
        path = item["trajectory_csv"]

        # 如果指定 prefer_root，则优先保留这个 root 下的
        preferred = 0
        if prefer_root is not None:
            try:
                path.relative_to(prefer_root)
                preferred = -1
            except ValueError:
                preferred = 0

        return (preferred, natural_key(path))

    removed_count = 0

    for group_idx, (digest, items) in enumerate(sorted(duplicate_groups.items()), start=1):
        items_sorted = sorted(items, key=keep_sort_key)
        keep_item = items_sorted[0]
        dup_items = items_sorted[1:]

        keep_traj = keep_item["trajectory_csv"]
        keep_run_dir = keep_item["run_dir"]

        for dup in dup_items:
            dup_traj = dup["trajectory_csv"]
            dup_run_dir = dup["run_dir"]

            action_result = "kept_check_only"
            moved_to = ""

            if args.action == "move":
                # 为了保留原路径信息，把重复目录移动到 duplicate_dir 下的相对结构
                try:
                    relative_parent = dup_run_dir.parent
                    for root in roots:
                        try:
                            relative_parent = dup_run_dir.parent.relative_to(root)
                            break
                        except ValueError:
                            continue

                    target = duplicate_dir / relative_parent / dup_run_dir.name
                    final_dst = safe_move_dir(dup_run_dir, target)
                    action_result = "moved"
                    moved_to = str(final_dst)
                    removed_count += 1
                except Exception as exc:
                    action_result = f"move_failed: {exc}"

            elif args.action == "delete":
                try:
                    shutil.rmtree(dup_run_dir)
                    action_result = "deleted"
                    removed_count += 1
                except Exception as exc:
                    action_result = f"delete_failed: {exc}"

            report_rows.append(
                {
                    "duplicate_group": group_idx,
                    "hash": digest,
                    "row_count": dup["row_count"],
                    "keep_trajectory": str(keep_traj),
                    "keep_run_dir": str(keep_run_dir),
                    "duplicate_trajectory": str(dup_traj),
                    "duplicate_run_dir": str(dup_run_dir),
                    "action": action_result,
                    "moved_to": moved_to,
                }
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "duplicate_group",
            "hash",
            "row_count",
            "keep_trajectory",
            "keep_run_dir",
            "duplicate_trajectory",
            "duplicate_run_dir",
            "action",
            "moved_to",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    if errors:
        error_path = report_path.with_suffix(".errors.json")
        error_path.write_text(
            json.dumps(
                [{"path": str(p), "error": e} for p, e in errors],
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"[WARN] failed to read {len(errors)} files, see: {error_path}")

    print(f"[INFO] report written: {report_path}")

    if args.action == "check":
        print("[INFO] check only. No files were moved or deleted.")
        print("[INFO] After reviewing the report, rerun with --action move.")
    else:
        print(f"[INFO] removed duplicate run dirs: {removed_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
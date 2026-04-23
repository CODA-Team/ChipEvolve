#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

from flow_paths import normalize_flow_relative, resolve_flow_path


def legacy_identity(snapshot_path: Path, summary_path: Path, output_coords: Path, output_manifest: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with snapshot_path.open("r", encoding="utf-8") as src, output_coords.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in reader:
            writer.writerow(row)

    manifest = {
        "status": "placeholder",
        "mode": "identity",
        "message": (
            "This legacy path keeps the old snapshot/summary contract alive. "
            "Use --dreamplace-input for the actual Abacus bridge."
        ),
        "snapshot": normalize_flow_relative(snapshot_path),
        "summary": summary,
        "output_coords": normalize_flow_relative(output_coords),
    }
    output_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def append_package_build_path(build_root: Path, package_name: str, op_name: str) -> None:
    package = __import__(package_name, fromlist=["__path__"])
    build_path = build_root / "build" / "dreamplace" / "ops" / op_name
    if not build_path.exists():
        raise FileNotFoundError(f"Missing DREAMPlace build directory for {op_name}: {build_path}")
    build_path_str = str(build_path)
    if build_path_str not in package.__path__:
        package.__path__.append(build_path_str)


def load_dreamplace_modules(root: Path):
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))

    import dreamplace_vendor.ops.abacus_legalize
    import dreamplace_vendor.ops.greedy_legalize
    import dreamplace_vendor.ops.legality_check

    append_package_build_path(root, "dreamplace_vendor.ops.abacus_legalize", "abacus_legalize")
    append_package_build_path(root, "dreamplace_vendor.ops.greedy_legalize", "greedy_legalize")
    append_package_build_path(root, "dreamplace_vendor.ops.legality_check", "legality_check")

    import dreamplace_vendor.ops.abacus_legalize.abacus_legalize as abacus_legalize
    import dreamplace_vendor.ops.greedy_legalize.greedy_legalize as greedy_legalize
    import dreamplace_vendor.ops.legality_check.legality_check as legality_check
    import torch

    return torch, greedy_legalize, abacus_legalize, legality_check


def build_region_tensors(torch_mod, payload):
    regions = payload.get("regions", [])
    flat_boxes: list[float] = []
    flat_starts = [0]
    for region in regions:
        boxes = region.get("boxes", [])
        for box in boxes:
            flat_boxes.extend(box)
        flat_starts.append(flat_starts[-1] + len(boxes))

    if flat_boxes:
        flat_region_boxes = torch_mod.tensor(flat_boxes, dtype=torch_mod.float64)
    else:
        flat_region_boxes = torch_mod.empty((0,), dtype=torch_mod.float64)
    flat_region_boxes_start = torch_mod.tensor(flat_starts, dtype=torch_mod.int32)
    return flat_region_boxes, flat_region_boxes_start


def snap_to_grid(value: float, origin: float, step: float) -> float:
    if step <= 0:
        return value
    return origin + math.floor(((value - origin) / step) + 0.5) * step


def clamp(value: float, lower: float, upper: float) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def row_id_for_y(y_value: float, yl: float, row_height: float) -> int:
    if row_height <= 0:
        return 0
    return int(round((y_value - yl) / row_height))


def run_abacus(payload: dict, dreamplace_root: Path, output_coords: Path, output_manifest: Path) -> None:
    torch_mod, greedy_legalize, abacus_legalize, legality_check = load_dreamplace_modules(dreamplace_root)

    nodes = payload["nodes"]
    movable_nodes = [node for node in nodes if not int(node["is_fixed"])]
    fixed_nodes = [node for node in nodes if int(node["is_fixed"])]
    ordered_nodes = movable_nodes + fixed_nodes
    num_movable_nodes = len(movable_nodes)
    num_fixed_nodes = len(fixed_nodes)

    xl = float(payload["xl"])
    yl = float(payload["yl"])
    xh = float(payload["xh"])
    yh = float(payload["yh"])
    site_width = float(payload["site_width"])
    row_height = float(payload["row_height"])
    num_bins_x = int(payload.get("num_bins_x", 1))
    num_bins_y = int(payload.get("num_bins_y", 64))

    init_x = [float(node["x"]) for node in ordered_nodes]
    init_y = [float(node["y"]) for node in ordered_nodes]
    pos_x: list[float] = []
    pos_y: list[float] = []
    fixed_intervals_by_row: dict[int, list[tuple[float, float]]] = {}
    movable_by_row: dict[int, list[tuple[int, float, float]]] = {}
    for node_id, node in enumerate(ordered_nodes):
        x_value = float(node["x"])
        y_value = float(node["y"])
        width = float(node["width"])
        height = float(node["height"])
        if not int(node["is_fixed"]):
            y_value = snap_to_grid(y_value, yl, row_height)
            y_value = clamp(y_value, yl, yh - height)
            row_id = row_id_for_y(y_value, yl, row_height)
            movable_by_row.setdefault(row_id, []).append((node_id, x_value + width / 2.0, width))
        else:
            row_id = row_id_for_y(y_value, yl, row_height)
            fixed_intervals_by_row.setdefault(row_id, []).append((x_value, x_value + width))
        pos_x.append(x_value)
        pos_y.append(y_value)

    for row_id, row_nodes in movable_by_row.items():
        fixed_intervals = sorted(fixed_intervals_by_row.get(row_id, []))
        cursor = xl
        for node_id, _, width in sorted(row_nodes, key=lambda item: (item[1], item[0])):
            x_value = clamp(pos_x[node_id], xl, xh - width)
            x_value = max(x_value, cursor)
            while True:
                advanced = False
                for fixed_xl, fixed_xh in fixed_intervals:
                    if x_value + width <= fixed_xl or x_value >= fixed_xh:
                        continue
                    x_value = fixed_xh
                    advanced = True
                    break
                if not advanced:
                    break
            x_value = clamp(x_value, xl, xh - width)
            pos_x[node_id] = x_value
            cursor = x_value + width

    node_size_x = [float(node["width"]) for node in ordered_nodes]
    node_size_y = [float(node["height"]) for node in ordered_nodes]
    node_weights = [float(node.get("pin_weight", 1.0)) for node in ordered_nodes]

    init_pos = torch_mod.tensor(init_x + init_y, dtype=torch_mod.float64)
    pos = torch_mod.tensor(pos_x + pos_y, dtype=torch_mod.float64)
    node_size_x_t = torch_mod.tensor(node_size_x, dtype=torch_mod.float64)
    node_size_y_t = torch_mod.tensor(node_size_y, dtype=torch_mod.float64)
    node_weights_t = torch_mod.tensor(node_weights, dtype=torch_mod.float64)

    flat_region_boxes, flat_region_boxes_start = build_region_tensors(torch_mod, payload)
    sentinel_region = int(payload.get("sentinel_region", 1000000))
    node2fence_region_map = torch_mod.tensor(
        [int(node.get("region_id", sentinel_region)) for node in movable_nodes],
        dtype=torch_mod.int32,
    )

    start_time = time.time()
    greedy = greedy_legalize.GreedyLegalize(
        node_size_x=node_size_x_t,
        node_size_y=node_size_y_t,
        node_weights=node_weights_t,
        flat_region_boxes=flat_region_boxes,
        flat_region_boxes_start=flat_region_boxes_start,
        node2fence_region_map=node2fence_region_map,
        xl=xl,
        yl=yl,
        xh=xh,
        yh=yh,
        site_width=site_width,
        row_height=row_height,
        num_bins_x=num_bins_x,
        num_bins_y=num_bins_y,
        num_movable_nodes=num_movable_nodes,
        num_terminal_NIs=0,
        num_filler_nodes=0,
    )
    abacus = abacus_legalize.AbacusLegalize(
        node_size_x=node_size_x_t,
        node_size_y=node_size_y_t,
        node_weights=node_weights_t,
        flat_region_boxes=flat_region_boxes,
        flat_region_boxes_start=flat_region_boxes_start,
        node2fence_region_map=node2fence_region_map,
        xl=xl,
        yl=yl,
        xh=xh,
        yh=yh,
        site_width=site_width,
        row_height=row_height,
        num_bins_x=num_bins_x,
        num_bins_y=num_bins_y,
        num_movable_nodes=num_movable_nodes,
        num_terminal_NIs=0,
        num_filler_nodes=0,
    )

    legality = legality_check.LegalityCheck(
        node_size_x=node_size_x_t,
        node_size_y=node_size_y_t,
        flat_region_boxes=flat_region_boxes,
        flat_region_boxes_start=flat_region_boxes_start,
        node2fence_region_map=node2fence_region_map,
        xl=xl,
        yl=yl,
        xh=xh,
        yh=yh,
        site_width=site_width,
        row_height=row_height,
        scale_factor=1.0,
        num_terminals=num_fixed_nodes,
        num_movable_nodes=num_movable_nodes,
    )
    greedy_output = greedy(pos, pos).cpu()
    greedy_legal = bool(legality(greedy_output))
    output = abacus(pos, greedy_output).cpu()
    runtime_seconds = time.time() - start_time
    legal = bool(legality(output))

    num_nodes = len(ordered_nodes)
    out_x = output[:num_nodes].tolist()
    out_y = output[num_nodes:].tolist()

    output_coords.parent.mkdir(parents=True, exist_ok=True)
    with output_coords.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "inst",
            "master",
            "x",
            "y",
            "orient",
            "width",
            "height",
            "status",
            "is_placed",
            "is_fixed",
            "pin_weight",
            "region_id",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for node, x_value, y_value in zip(ordered_nodes, out_x, out_y):
            writer.writerow(
                {
                    "inst": node["inst"],
                    "master": node["master"],
                    "x": int(round(x_value)),
                    "y": int(round(y_value)),
                    "orient": node["orient"],
                    "width": int(node["width"]),
                    "height": int(node["height"]),
                    "status": node["status"],
                    "is_placed": 1,
                    "is_fixed": int(node["is_fixed"]),
                    "pin_weight": node.get("pin_weight", 1),
                    "region_id": node.get("region_id", payload.get("sentinel_region", 1000000)),
                }
            )

    manifest = {
        "status": "ok" if legal else "illegal",
        "mode": "dreamplace_abacus",
        "dreamplace_root": str(dreamplace_root),
        "runtime_seconds": runtime_seconds,
        "greedy_legality_check_passed": greedy_legal,
        "legality_check_passed": legal,
        "num_movable_nodes": num_movable_nodes,
        "num_fixed_nodes": num_fixed_nodes,
        "num_regions": len(payload.get("regions", [])),
        "pre_snap_to_rows": True,
        "output_coords": normalize_flow_relative(output_coords),
    }
    output_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if not legal:
        raise SystemExit("DreamPlace Abacus returned illegal coordinates.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run DREAMPlace Abacus legalization on an exported ODB snapshot."
    )
    parser.add_argument("--dreamplace-input", help="JSON export created by export_dreamplace_input.tcl.")
    parser.add_argument("--snapshot", help="Legacy input snapshot TSV.")
    parser.add_argument("--summary", help="Legacy input snapshot summary JSON.")
    parser.add_argument(
        "--dreamplace-root",
        default=os.environ.get("DREAMPLACE_ROOT", "/opt/EDAs/DREAMPlace"),
        help="DREAMPlace checkout root. Default: DREAMPLACE_ROOT or /opt/EDAs/DREAMPlace",
    )
    parser.add_argument(
        "--output-coords",
        required=True,
        help="Output TSV path for legalized coordinates.",
    )
    parser.add_argument(
        "--output-manifest",
        required=True,
        help="Output JSON manifest describing the bridge run.",
    )
    args = parser.parse_args()

    output_coords = resolve_flow_path(args.output_coords)
    output_manifest = resolve_flow_path(args.output_manifest)
    output_coords.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    dreamplace_root = resolve_flow_path(args.dreamplace_root)

    if args.dreamplace_input:
        payload = json.loads(resolve_flow_path(args.dreamplace_input).read_text(encoding="utf-8"))
        run_abacus(payload, dreamplace_root, output_coords, output_manifest)
        return

    if args.snapshot and args.summary:
        legacy_identity(
            resolve_flow_path(args.snapshot),
            resolve_flow_path(args.summary),
            output_coords,
            output_manifest,
        )
        return

    raise SystemExit("Provide --dreamplace-input for the real bridge, or --snapshot/--summary for the legacy identity mode.")


if __name__ == "__main__":
    main()

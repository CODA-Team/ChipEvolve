"""Apply explicit design ranges to initial perturbations, preserving row-one baseline."""

import argparse
import csv
from pathlib import Path

from common import get_design_config, load_config


def constrain(path: Path, config: dict, platform: str, design: str) -> None:
    design_config = get_design_config(config, platform, design) or {}
    overrides = design_config.get("placement_range_override", {})
    if not overrides:
        return
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = list(reader)
    for row in rows[1:]:
        for name, (low, high) in overrides.items():
            if name in row:
                value = max(low, min(high, float(row[name])))
                kind = config["parameter_constraints"]["placement"][name]["type"]
                row[name] = str(int(value) if kind == "int" else value)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("platform")
    parser.add_argument("design")
    args = parser.parse_args()
    constrain(args.csv, load_config(Path("drp_config.json")), args.platform, args.design)

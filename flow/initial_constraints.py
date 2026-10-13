"""Apply explicit design ranges to initial perturbations, preserving row-one baseline."""

import argparse
import csv
import json
from pathlib import Path


def constrain(path: Path, config: dict, platform: str, design: str) -> None:
    design_config = next((c for c in config["configurations"]
                          if c["platform"] == platform and c["design"] == design), {})
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
    config_path = Path(__file__).with_name("drp_config.json")
    constrain(args.csv, json.loads(config_path.read_text()), args.platform, args.design)

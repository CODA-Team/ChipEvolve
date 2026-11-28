"""Keep historical product wheels out of the final offline dependency directory."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--sprint", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--filtered-dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--filter-record", type=Path, required=True)
    args = parser.parse_args()
    wheels = json.loads((args.sprint / "packages-freeze-v1/manifest.json").read_text())[
        "wheels"
    ]
    products = {name.split("-", 1)[0] for name in wheels}
    args.filtered_dependencies.mkdir(parents=True, exist_ok=False)
    kept, skipped = [], []
    for path in sorted(args.dependencies.glob("*.whl")):
        row = {
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if path.name.split("-", 1)[0] in products:
            skipped.append(row)
        else:
            shutil.copyfile(path, args.filtered_dependencies / path.name)
            kept.append(row)
    if not kept:
        raise ValueError("No third-party dependencies retained")
    with args.filter_record.open("x") as stream:
        json.dump(
            {
                "third_party_dependencies": kept,
                "historical_product_wheels_excluded": skipped,
                "product_packages": "Only the 11 frozen product wheels in packages/ are distributed",
                "original_wheelhouse_modified": False,
                "program_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    command = [
        sys.executable,
        str(Path(__file__).with_name("build_code_delivery.py")),
        "--workspace",
        str(args.workspace),
        "--sprint",
        str(args.sprint),
        "--dependencies",
        str(args.filtered_dependencies),
        "--output",
        str(args.output),
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()

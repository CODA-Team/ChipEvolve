"""Build identifiable development wheels without replacing running venvs."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    packages = [
        root / "execution-foundation" / name
        for name in (
            "contracts",
            "core/client",
            "core/runtime",
            "core/registry",
            "core/evaluator",
            "core/provenance",
            "gateway",
        )
    ]
    packages.extend(
        root / name
        for name in (
            "toolkits",
            "data-foundation",
            "data-interface",
            "agent/query-agent",
        )
    )
    commits = {}
    for path in packages:
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--", "."], cwd=path, text=True
        )
        if status:
            parser.error(
                f"Release wheel source must be committed: {path.relative_to(root)}"
            )
        commits[path] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip()

    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    env = dict(os.environ, PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    receipts = []
    for path, commit in commits.items():
        command = [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(output),
            str(path),
        ]
        subprocess.run(command, env=env, check=True)
        receipts.append({"source": str(path), "commit": commit, "command": command})
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob("*.whl"))
    }
    (output / "manifest.json").write_text(
        json.dumps({"wheels": hashes, "builds": receipts}, indent=2) + "\n"
    )
    print(json.dumps({"built_wheels": len(hashes), "destination": str(output)}))


if __name__ == "__main__":
    main()

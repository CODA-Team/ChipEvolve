"""Identify physical tools independently of host startup wrappers."""

import hashlib
import json
import subprocess
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tool_fingerprint(profile):
    if "runtime" not in profile:
        return {name: digest(profile[name]) for name in ("openroad_bin", "yosys_bin")}
    runtime = profile["runtime"]
    identity = profile["toolchain"]
    if runtime["kind"] != "apptainer":
        raise ValueError("unsupported Flow runtime")
    if digest(runtime["image"]) != identity["image_sha256"]:
        raise ValueError("common image changed; start a new experiment")
    if digest(identity["source_manifest_path"]) != identity["source_manifest_sha256"]:
        raise ValueError("common source manifest changed")
    paths = {name: row["path"] for name, row in identity["binaries"].items()}
    if any(profile[name + "_bin"] != paths[name] for name in ("openroad", "yosys")):
        raise ValueError("Flow tool paths differ from the frozen identity")
    script = (
        "import json,hashlib;from pathlib import Path;import sys;"
        'print(json.dumps({name:{"path":path,"sha256":hashlib.sha256('
        "Path(path).read_bytes()).hexdigest()} "
        "for name,path in json.loads(sys.argv[1]).items()}))"
    )
    observed = json.loads(
        subprocess.check_output(
            [
                runtime["executable"],
                "exec",
                "--cleanenv",
                "--containall",
                runtime["image"],
                "/usr/bin/python3",
                "-c",
                script,
                json.dumps(paths),
            ],
            text=True,
            timeout=60,
        )
    )
    if observed != identity["binaries"]:
        raise ValueError("actual tools differ from the frozen identity")
    return {**identity, "runtime": runtime, "binaries": observed}

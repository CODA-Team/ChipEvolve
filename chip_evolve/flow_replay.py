"""Re-route a selected Flow candidate from its recorded native placement."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import digest


def replay(
    deployment: Deployment, result_path: Path, experiment: Path
) -> dict[str, Any]:
    from .delivery import checkpoint, finish
    from .professional import flatten_archive

    frame = read(result_path)
    paths = [result_path] + [
        Path(frame[key])
        for key in ("flow_archive", "native_config", "flow_recipe", "objective")
    ]
    identity = {"input_hashes": {str(path): digest(path) for path in paths}}
    saved = experiment / "flow-replay-inputs.json"
    if saved.exists() and read(saved) != identity:
        raise ValueError("Flow replay inputs changed after the first attempt")
    inputs = experiment / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    write(saved, identity)
    archive = experiment / "source-checkpoint.zip"
    if not archive.exists():
        flatten_archive(Path(frame["flow_archive"]), archive)
    placement = inputs / "placement.odb"
    if not placement.exists():
        with zipfile.ZipFile(archive) as bundle:
            placement.write_bytes(bundle.read("flow/results/3_place.odb"))
    checkpoint(
        experiment,
        design_id=frame["design_id"],
        odb=placement,
        producer=frame["physical_run_id"],
        objective=Path(frame["objective"]),
        source=result_path,
        native_method={
            "kind": "independent-flow-routing-replay",
            "original_result": str(result_path),
            "candidate_id": frame["candidate_id"],
            "scope": "native pre-CTS placement through CTS, full route, RCX and common measurement",
            "native_search_restarted": False,
        },
    )
    return finish(deployment, experiment)

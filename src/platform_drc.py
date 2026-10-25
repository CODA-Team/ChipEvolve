"""Keep the selected routed state and its matching DRC evidence together."""

import hashlib
import os
from pathlib import Path


def routed_wns_improves(wns: float | None, best_qor: dict) -> bool:
    """Apply the native WNS ranking to every routed candidate, including first."""
    best_wns = best_qor.get("wns")
    return wns is not None and (best_wns is None or wns > best_wns)


def best_drc_report_tcl(report: str) -> str:
    if os.environ.get("TIMINGECO_EF_LEAF") != "1":
        return (
            f'set _drc_fp [open "{report}" w]; close $_drc_fp\n'
            f'tee -file "{report}" {{ check_drc }}\n'
        )
    return (
        "set _native_drc_count [drt::detailed_route_num_drvs]\n"
        f'set _drc_fp [open "{report}.count" w]\n'
        "puts $_drc_fp $_native_drc_count; close $_drc_fp\n"
        f'set _drc_fp [open "{report}" w]\n'
        'puts $_drc_fp "Native detailed-route violations: $_native_drc_count"\n'
        "close $_drc_fp\n"
    )


def route_evidence(
    output: Path, input_route_drc: int | None, *, input_checkpoint: Path
) -> dict:
    counter = output / "final_drc_report.txt.count"
    if counter.exists():
        count = int(counter.read_text().strip())
        origin = "native detailed-route counter saved at best selection"
    else:
        if (output / "final_eco.odb").read_bytes() != input_checkpoint.read_bytes():
            raise ValueError("Changed ECO checkpoint has no native route DRC counter")
        count = input_route_drc
        origin = "input baseline retained; no improving DRT candidate selected"
    with (output / "final_eco.odb").open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"checkpoint_sha256": sha, "route_drc": count, "origin": origin}

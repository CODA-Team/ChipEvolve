"""Test-only import timing around the installed clean Data Foundation wheel."""

import json
import runpy
import sys
import time
from pathlib import Path

from openroad_app_data_foundation.repository import DataStore

state = Path(sys.argv[sys.argv.index("--db") + 1]).parent
register = DataStore.register_import


def measured_import(self, artifact_id, pack):
    def record(event):
        with (state / "data-writes.jsonl").open("a") as out:
            out.write(
                json.dumps(
                    {
                        "event": event,
                        "wall": time.time(),
                        "artifact_id": artifact_id,
                        "snapshot_id": pack["snapshot"]["snapshot_id"],
                        "design_id": pack["snapshot"]["design_id"],
                    }
                )
                + "\n"
            )

    record("started")
    try:
        result = register(self, artifact_id, pack)
    except BaseException:
        record("failed")
        raise
    record("completed")
    return result


DataStore.register_import = measured_import
runpy.run_module("openroad_app_data_foundation", run_name="__main__")

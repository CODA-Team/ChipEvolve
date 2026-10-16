"""Isolated gateway instrumentation; never loaded by the production service."""

import faulthandler
import json
import runpy
import signal
import sys
import time
from pathlib import Path

from openroad_platform_runtime import RuntimeStore

state = Path(sys.argv[sys.argv.index("--state-root") + 1])
state.mkdir(parents=True, exist_ok=True)
faulthandler.register(signal.SIGUSR1, all_threads=True)
custody = RuntimeStore._store_object
heartbeat = RuntimeStore.heartbeat


def slow_bundle(self, path, digest, size):
    if path.name.startswith("runtime-bundle-"):
        (state / "slow-custody.json").write_text(
            json.dumps({"entered_at": time.time(), "delay_seconds": 35})
        )
        time.sleep(35)
    return custody(self, path, digest, size)


def measured_heartbeat(self, attempt_id, **kwargs):
    started = time.monotonic()
    error = None
    try:
        return heartbeat(self, attempt_id, **kwargs)
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        with (state / "heartbeats.jsonl").open("a") as out:
            out.write(
                json.dumps(
                    {
                        "wall": time.time(),
                        "attempt_id": attempt_id,
                        "elapsed": time.monotonic() - started,
                        "error": error,
                    }
                )
                + "\n"
            )


RuntimeStore._store_object = slow_bundle
RuntimeStore.heartbeat = measured_heartbeat
runpy.run_module("openroad_platform_gateway", run_name="__main__")

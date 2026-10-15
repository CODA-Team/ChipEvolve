#!/usr/bin/env python3
"""Single-machine business operations consumed by Codex."""

import json
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    local_hosts = "127.0.0.1,localhost,::1"
    bypass = os.environ.get("NO_PROXY", os.environ.get("no_proxy", ""))
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = local_hosts + "," + bypass
    if "--config" in sys.argv:
        config = Path(sys.argv[sys.argv.index("--config") + 1])
        python = Path(json.loads(config.read_text())["client_python"])
        if Path(sys.prefix) != python.parent.parent:
            os.execv(str(python), [str(python), *sys.argv])
    from chip_evolve.cli import main

    raise SystemExit(main())

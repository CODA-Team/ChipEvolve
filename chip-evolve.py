#!/usr/bin/env python3
"""Single-machine business operations consumed by Codex."""

import json
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    if "--config" in sys.argv:
        config = Path(sys.argv[sys.argv.index("--config") + 1])
        python = Path(json.loads(config.read_text())["client_python"])
        if Path(sys.prefix) != python.parent.parent:
            os.execv(str(python), [str(python), *sys.argv])
    from chip_evolve.cli import main

    raise SystemExit(main())

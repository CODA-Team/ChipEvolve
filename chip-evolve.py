#!/usr/bin/env python3
"""Single-machine business operations consumed by Codex."""

import argparse
import json
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    local_hosts = "127.0.0.1,localhost,::1"
    bypass = os.environ.get("NO_PROXY", os.environ.get("no_proxy", ""))
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = local_hosts + "," + bypass
    bootstrap = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    bootstrap.add_argument("--config", type=Path)
    options, _ = bootstrap.parse_known_args()
    if options.config is not None:
        python = Path(json.loads(options.config.read_text())["client_python"])
        if Path(sys.prefix).resolve() != python.parent.parent.resolve() or not (
            sys.flags.ignore_environment and sys.flags.no_user_site
        ):
            for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE"):
                os.environ.pop(key, None)
            os.execv(str(python), [str(python), "-E", "-s", *sys.argv])
    from chip_evolve.cli import main

    raise SystemExit(main())

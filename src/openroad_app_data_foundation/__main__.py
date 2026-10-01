"""Process entry point for the design-data service."""

from __future__ import annotations

import argparse

from .artifacts import DEFAULT_NATIVE_ROOT
from .repository import DataStore
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Design Data Foundation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8860)
    parser.add_argument("--db", default="data-foundation.db")
    parser.add_argument("--kernel-url", default=None)
    parser.add_argument("--kernel-token", default=None)
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT),
                        help="the flow tree holding the run's own results/reports/logs")
    parser.add_argument("--no-auto-import", action="store_true")
    args = parser.parse_args(argv)
    store = DataStore(args.db)
    try:
        serve(host=args.host, port=args.port, store=store, kernel_url=args.kernel_url,
              kernel_token=args.kernel_token, auto_import=not args.no_auto_import,
              native_root=args.native_root)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

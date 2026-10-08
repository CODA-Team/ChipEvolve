"""Process entry point for the design-data service."""

from __future__ import annotations

import argparse
from pathlib import Path

from .artifacts import DEFAULT_NATIVE_ROOT
from .repository import DataStore
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Design Data Foundation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8860)
    parser.add_argument("--db", default="data-foundation.db")
    parser.add_argument("--archive-db", action="append", default=[],
                        help="explicit historical DB exposed read-only; writes stay in --db")
    parser.add_argument("--kernel-url", default=None)
    parser.add_argument("--kernel-token", default=None)
    parser.add_argument("--archive-kernel-url", default=None,
                        help="read original artifact bytes from this archive execution service; never submit there")
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT),
                        help="the flow tree holding the run's own results/reports/logs")
    parser.add_argument("--no-auto-import", action="store_true")
    parser.add_argument("--read-only", action="store_true",
                        help="explicitly serve an existing database without importing or modifying it")
    args = parser.parse_args(argv)
    if args.read_only and not args.no_auto_import:
        parser.error('--read-only requires --no-auto-import')
    if not args.read_only:
        Path(args.db).expanduser().parent.mkdir(parents=True, exist_ok=True)
    store = DataStore(args.db, read_only=args.read_only, archives=args.archive_db)
    try:
        serve(host=args.host, port=args.port, store=store, kernel_url=args.kernel_url,
              kernel_token=args.kernel_token, archive_kernel_url=args.archive_kernel_url, auto_import=not args.no_auto_import,
              native_root=args.native_root)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

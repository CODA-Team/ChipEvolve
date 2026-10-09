"""Run the platform: python3 -m openroad_platform_gateway --state-root ...

One local process serves the kernel API and a worker. No account or app config.
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from openroad_platform_runtime import RuntimeWorker

from .app import build_router
from .bootstrap import KernelPaths, build_kernel
from .router import make_handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openroad-platform-gateway")
    parser.add_argument(
        "--state-root",
        required=True,
        help="directory holding the kernel's durable state",
    )
    parser.add_argument(
        "--plugins-root",
        default="plugins",
        help="directory scanned for plugin manifests",
    )
    parser.add_argument(
        "--admissions-root",
        default="admissions",
        help="directory holding the platform's own trust records",
    )
    parser.add_argument("--capacity-cpu-cores", type=int)
    parser.add_argument("--capacity-memory-bytes", type=int)
    parser.add_argument("--worker-concurrency", type=int, default=1)
    parser.add_argument("--platform-fraction", type=float, default=0.60)
    parser.add_argument(
        "--input-root",
        action="append",
        default=[],
        help="allowed root for caller-provided host inputs; repeatable",
    )
    parser.add_argument(
        "--api-only", action="store_true", help="use a separately managed worker"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8700)
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "::1", "localhost"):
        parser.error("this single-user service binds only to loopback")
    kernel = build_kernel(
        KernelPaths.of(
            args.state_root,
            args.plugins_root,
            args.admissions_root,
            capacity_cpu_cores=args.capacity_cpu_cores,
            capacity_memory_bytes=args.capacity_memory_bytes,
            platform_fraction=args.platform_fraction,
            input_roots=tuple(args.input_root),
        ),
    )
    router = build_router(kernel)

    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer((args.host, args.port), make_handler(router))
    stop = threading.Event()
    worker = RuntimeWorker(kernel.store, kernel.runtime, idle_seconds=0.1, batch=args.worker_concurrency)
    thread = (
        None
        if args.api_only
        else threading.Thread(
            target=worker.serve_forever,
            args=(stop,),
            name="local-worker",
        )
    )
    if thread is not None:
        thread.start()

    def shutdown(signum, frame):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        server.serve_forever()
    finally:
        stop.set()
        if thread is not None:
            thread.join()
        server.server_close()
        kernel.store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

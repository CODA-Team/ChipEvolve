"""A small pool of read-only connections, so readers do not queue behind one lock.

Measured on the served interface against the real 44 GB ariane136 store, before
this existed:

    clients   req/s   throughput x   p50 ms   p50 x
          1  1506.9           1.00    0.597    1.00
          2  1764.1           1.17    1.091    1.83
          4  1739.8           1.15    2.269    3.80
          8  1687.5           1.12    4.687    7.85

Throughput stops at 1.12x of a single client while median latency grows 7.85x, and
the same serialisation shows up as head-of-line blocking: a request the store
answers in 0.6 ms waited **14,679 ms** behind one net-context request.

The cause was one shared `sqlite3.Connection` behind one `RLock`, with a request
lock on top.  SQLite serves concurrent readers happily; the service only had to
stop putting every request through one connection.

**Not one connection per request thread.**  `ThreadingHTTPServer` starts a thread
per TCP connection, not per client, so a thread-local connection meant a fresh
SQLite connection - file open, mmap, pragmas - for every request, and throughput
at eight clients fell to 0.20x.  The pool below is bounded and reuses its
connections instead.  Writes still go through the single writable store.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .repository import DataStore

#: How many read connections may exist at once.  Past this, extra callers queue
#: for a connection rather than opening one; the ceiling is the interpreter, not
#: SQLite, so a larger pool does not buy throughput.
DEFAULT_POOL_SIZE = 8


class ReadPool:
    """Bounded, reused read-only connections."""

    def __init__(self, path: str | Path, size: int = DEFAULT_POOL_SIZE) -> None:
        self._path = str(path)
        self._size = size
        self._semaphore = threading.BoundedSemaphore(size)
        self._free: list[DataStore] = []
        self._lock = threading.Lock()
        self._opened = 0

    @contextmanager
    def connection(self) -> Iterator[DataStore]:
        """Borrow a read-only store for the duration of one request."""
        self._semaphore.acquire()
        store: DataStore | None = None
        try:
            with self._lock:
                if self._free:
                    store = self._free.pop()
                else:
                    store = DataStore(self._path, read_only=True)
                    self._opened += 1
            yield store
        finally:
            if store is not None:
                with self._lock:
                    self._free.append(store)
            self._semaphore.release()

    @property
    def opened(self) -> int:
        """Connections created so far (bounded by the pool size)."""
        return self._opened

    def close(self) -> None:
        with self._lock:
            for store in self._free:
                store.close()
            self._free.clear()

"""Attempt-scoped lease renewal independent of tool and artifact callbacks."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from types import TracebackType

from openroad_platform_contracts import RuntimeStatus

from .store import RuntimeStore


class LeasePulse:
    def __init__(
        self,
        store: RuntimeStore,
        run_id: str,
        attempt_id: str,
        *,
        worker_id: str,
        lease_seconds: int,
        timeout_seconds: float,
        external_cancel_requested: Callable[[], bool] | None = None,
    ):
        self.store, self.run_id, self.attempt_id = store, run_id, attempt_id
        self.worker_id, self.lease_seconds = worker_id, lease_seconds
        self.external_cancel_requested = external_cancel_requested
        self._stop = threading.Event()
        self._owner = threading.current_thread()
        # The normal tool deadline still belongs to the guardian. This bounds
        # renewal if a lifecycle callback never returns, including after exit.
        self._deadline = time.monotonic() + timeout_seconds + lease_seconds
        self._error: Exception | None = None
        self._thread = threading.Thread(
            target=self._renew,
            name=f"lease-{attempt_id}",
            daemon=True,
        )

    def __enter__(self) -> LeasePulse:
        self._heartbeat()
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._stop.set()
        self._thread.join()

    def _heartbeat(self) -> None:
        self.store.heartbeat(
            self.attempt_id,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )

    def _renew(self) -> None:
        while not self._stop.wait(self.lease_seconds / 3):
            if not self._owner.is_alive():
                return
            if time.monotonic() >= self._deadline:
                self._error = TimeoutError(
                    "attempt lifecycle exhausted its renewal budget"
                )
                return
            try:
                self._heartbeat()
            except Exception as error:
                # Surface renewal failures on the owning control path. Never
                # pretend the attempt still owns a lease after being fenced.
                self._error = error
                return

    def check(self) -> None:
        if self._error is not None:
            raise self._error

    def __call__(self) -> bool:
        self.check()
        if (
            self.external_cancel_requested is not None
            and self.external_cancel_requested()
        ):
            self.store.request_cancel(self.run_id)
            return True
        return self.store.get_run(self.run_id).status is RuntimeStatus.CANCEL_REQUESTED

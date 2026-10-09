"""Versioned atomic checkpoints with optimistic concurrency and append-only history."""

from __future__ import annotations

import fcntl
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from query_agent.domain.investigation import InvestigationState


class ConcurrentInvestigationUpdate(RuntimeError):
    """A second host edited this state; reload before proposing another action."""


class JsonInvestigationStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _folder(self, investigation_id: str) -> Path:
        if (
            not investigation_id
            or not investigation_id.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError("investigation_id must be an alphanumeric identifier")
        return self.root / investigation_id

    @contextmanager
    def _lock(self, folder: Path) -> Generator[None]:
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "state.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self, investigation_id: str) -> InvestigationState:
        folder = self._folder(investigation_id)
        with self._lock(folder):
            return InvestigationState.model_validate_json(
                (folder / "state.json").read_text()
            )

    def save(self, state: InvestigationState, expected_revision: int) -> None:
        folder = self._folder(state.investigation_id)
        with self._lock(folder):
            current = folder / "state.json"
            previous = (
                InvestigationState.model_validate_json(current.read_text())
                if current.exists()
                else None
            )
            actual = previous.revision if previous is not None else 0
            if expected_revision != actual:
                raise ConcurrentInvestigationUpdate(
                    "checkpoint revision changed; reload investigation"
                )
            if previous is not None and (
                previous.question != state.question
                or previous.scopes != state.scopes[: len(previous.scopes)]
            ):
                raise ValueError(
                    "question and fixed scopes cannot change while resuming"
                )
            if previous is not None:
                for scope in state.scopes[len(previous.scopes) :]:
                    if scope.role != "supplement" or not any(
                        ticket.snapshot_id == scope.snapshot_id
                        and ticket.parent_snapshot_id == scope.parent_snapshot_id
                        and ticket.status == "imported"
                        for ticket in state.pending_analyses
                    ):
                        raise ValueError(
                            "new scope needs a successfully imported analysis"
                        )
            state.revision = actual + 1
            state.updated_at = datetime.now(UTC)
            payload = state.model_dump_json(indent=2)
            history = folder / "history"
            history.mkdir(exist_ok=True)
            (history / f"{state.revision:06d}.json").write_text(payload + "\n")
            temporary = folder / "state.tmp"
            temporary.write_text(payload + "\n")
            temporary.replace(current)
            with (folder / "journal.jsonl").open("a") as journal:
                journal.write(
                    json.dumps(
                        {
                            "revision": state.revision,
                            "status": state.status,
                            "updated_at": state.updated_at.isoformat(),
                            "steps_used": state.steps_used,
                        }
                    )
                    + "\n"
                )

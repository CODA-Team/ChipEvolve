"""Deterministic design-data indexing and query service."""

from .repository import DataStore

__all__ = ("DataStore",)


def source_fingerprint() -> str:
    """A hash of this package's own source, computed at process start.

    Deployment drift is a question about *content*: "was the running service built
    from the source that is checked out now?".  mtime answers a different question
    and answers it wrongly - a test run that imports a module can bump its mtime
    without changing a byte, which made a drift probe report drift for two rounds.
    """
    import hashlib
    from pathlib import Path as _Path

    root = _Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()

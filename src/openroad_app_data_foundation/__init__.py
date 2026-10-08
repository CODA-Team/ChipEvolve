"""Deterministic design-data indexing and query service."""
from .repository import DataStore

__all__ = ("DataStore",)


def source_fingerprint() -> str:
    """Hash this deployment's service and installed public contract/client code.

    External producer provenance belongs to imported snapshot artifacts, not
    to an assumed sibling source directory on the service host.
    """
    import hashlib
    from importlib.util import find_spec
    from pathlib import Path

    digest = hashlib.sha256()
    for name in ("openroad_app_data_foundation", "openroad_platform_contracts",
                 "openroad_platform_client"):
        spec = find_spec(name)
        if spec is None or not spec.submodule_search_locations:
            raise ImportError(name)
        for directory in spec.submodule_search_locations:
            base = Path(directory)
            for path in sorted(base.rglob("*.py")):
                if path.name.startswith("test_") or "__pycache__" in path.parts:
                    continue
                digest.update((name + "/" + path.relative_to(base).as_posix()).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()

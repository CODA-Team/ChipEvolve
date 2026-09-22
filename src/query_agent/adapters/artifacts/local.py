"""Safe, read-only local workspace artifact provider."""

from __future__ import annotations

import fnmatch
import mimetypes
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from query_agent.domain.capability import Capability
from query_agent.domain.errors import (
    ArtifactLimitError,
    ArtifactNotFoundError,
    ArtifactPathError,
    BinaryArtifactError,
)
from query_agent.domain.evidence import ArtifactExcerpt, ArtifactMetadata, TextMatch
from query_agent.domain.query import QueryContext, QuerySource

_BINARY_SUFFIXES = frozenset(
    {".bin", ".db", ".gds", ".gz", ".odb", ".pickle", ".tar", ".zip"}
)


class LocalArtifactProvider:
    """Read files under one workspace root, with no shell or write API."""

    def __init__(self, workspace_root: str | Path, *, max_read_bytes: int = 64 * 1024):
        root = Path(workspace_root).expanduser()
        if not root.exists() or not root.is_dir():
            raise ArtifactPathError(f"workspace root is not a directory: {root}")
        if max_read_bytes <= 0:
            raise ArtifactLimitError("max_read_bytes must be positive")
        self._root = root.resolve()
        self._max_read_bytes = max_read_bytes

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.ARTIFACT_DISCOVERY,
                Capability.TEXT_SEARCH,
                Capability.EXPLICIT_METRIC,
            }
        )

    def list_artifacts(self, context: QueryContext) -> Sequence[ArtifactMetadata]:
        self._validate_context(context)
        artifacts: list[ArtifactMetadata] = []
        for candidate in self._root.rglob("*"):
            relative = candidate.relative_to(self._root).as_posix()
            self._secure_path(relative, require_exists=False)
            if candidate.is_file():
                artifacts.append(self._metadata(candidate, relative))
        return tuple(sorted(artifacts, key=lambda item: item.path))

    def find_artifacts(
        self, context: QueryContext, pattern: str
    ) -> Sequence[ArtifactMetadata]:
        self._validate_pattern(pattern)
        return tuple(
            item
            for item in self.list_artifacts(context)
            if fnmatch.fnmatchcase(item.path, pattern)
            or fnmatch.fnmatchcase(Path(item.path).name, pattern)
        )

    def search_text(
        self, context: QueryContext, query: str, *, max_results: int = 50
    ) -> Sequence[TextMatch]:
        self._validate_context(context)
        if not query.strip():
            raise ValueError("text search query must not be blank")
        if max_results <= 0:
            raise ArtifactLimitError("max_results must be positive")

        matches: list[TextMatch] = []
        for artifact in self.list_artifacts(context):
            if artifact.is_binary:
                continue
            path = self._secure_path(artifact.path)
            raw = path.read_bytes()[: self._max_read_bytes]
            text = raw.decode("utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if query in line:
                    matches.append(
                        TextMatch(
                            path=artifact.path, line_number=line_number, line=line
                        )
                    )
                    if len(matches) >= max_results:
                        return tuple(matches)
        return tuple(matches)

    def read_excerpt(
        self,
        context: QueryContext,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int | None = None,
    ) -> ArtifactExcerpt:
        self._validate_context(context)
        if offset < 0:
            raise ArtifactLimitError("offset must be non-negative")
        limit = self._max_read_bytes if max_bytes is None else max_bytes
        if not 0 < limit <= self._max_read_bytes:
            raise ArtifactLimitError(
                f"max_bytes must be between 1 and {self._max_read_bytes}"
            )
        metadata = self.stat(context, path)
        if metadata.is_binary:
            raise BinaryArtifactError(f"binary artifact cannot be read as text: {path}")
        resolved = self._secure_path(path)
        with resolved.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read(limit + 1)
        content = raw[:limit].decode("utf-8", errors="replace")
        return ArtifactExcerpt(
            path=metadata.path,
            offset=offset,
            content=content,
            bytes_read=len(raw[:limit]),
            truncated=len(raw) > limit,
        )

    def stat(self, context: QueryContext, path: str) -> ArtifactMetadata:
        self._validate_context(context)
        resolved = self._secure_path(path)
        relative = resolved.relative_to(self._root).as_posix()
        if not resolved.exists():
            raise ArtifactNotFoundError(f"artifact does not exist: {path}")
        if not resolved.is_file():
            raise ArtifactNotFoundError(f"artifact is not a file: {path}")
        return self._metadata(resolved, relative)

    def _validate_context(self, context: QueryContext) -> None:
        if context.source is not QuerySource.LOCAL_WORKSPACE:
            raise ArtifactPathError(
                "LocalArtifactProvider cannot read a managed execution run"
            )
        if context.workspace is None:
            raise ArtifactPathError("local workspace context is required")
        context_root = Path(context.workspace).expanduser().resolve()
        if context_root != self._root:
            raise ArtifactPathError(
                f"query workspace {context.workspace} is not this provider root"
            )

    @staticmethod
    def _validate_pattern(pattern: str) -> None:
        if not pattern.strip():
            raise ArtifactPathError("artifact pattern must not be blank")
        pure = PurePosixPath(pattern)
        if pure.is_absolute() or ".." in pure.parts:
            raise ArtifactPathError("artifact pattern may not escape the workspace")

    def _secure_path(
        self,
        path: str,
        *,
        require_exists: bool = True,
    ) -> Path:
        if not path or "\x00" in path:
            raise ArtifactPathError("artifact path must be non-empty and NUL-free")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise ArtifactPathError("artifact path may not escape the workspace")
        candidate = self._root.joinpath(*pure.parts)
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise ArtifactPathError("artifact path escapes the workspace") from exc
        if require_exists and not resolved.exists():
            raise ArtifactNotFoundError(f"artifact does not exist: {path}")
        return resolved

    @staticmethod
    def _metadata(path: Path, relative: str) -> ArtifactMetadata:
        stat = path.stat()
        return ArtifactMetadata(
            path=relative,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            media_type=mimetypes.guess_type(relative)[0],
            is_binary=LocalArtifactProvider._is_binary(path),
        )

    @staticmethod
    def _is_binary(path: Path) -> bool:
        if path.suffix.lower() in _BINARY_SUFFIXES:
            return True
        sample = path.read_bytes()[:4096]
        if b"\x00" in sample:
            return True
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return True
        return False

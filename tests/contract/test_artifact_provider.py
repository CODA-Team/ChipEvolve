from pathlib import Path

import pytest

from query_agent.adapters.artifacts import LocalArtifactProvider
from query_agent.domain.errors import (
    ArtifactNotFoundError,
    ArtifactPathError,
    BinaryArtifactError,
)
from query_agent.domain.query import QueryContext


@pytest.fixture()
def workspace() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "sample_workspace"


@pytest.fixture()
def provider(workspace: Path) -> LocalArtifactProvider:
    return LocalArtifactProvider(workspace, max_read_bytes=32)


@pytest.fixture()
def context(workspace: Path) -> QueryContext:
    return QueryContext(workspace=workspace, design_id="sample", run_id="run-1")


def test_list_normal_files(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    paths = {item.path for item in provider.list_artifacts(context)}
    assert "config.mk" in paths
    assert "logs/place.log" in paths
    assert "results/final.def" in paths


def test_find_matching_files(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    found = provider.find_artifacts(context, "*.log")
    assert {item.path for item in found} == {"logs/place.log", "logs/route.log"}


def test_text_search_is_bounded_and_cited(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    matches = provider.search_text(context, "ERROR")
    assert len(matches) == 1
    assert matches[0].path == "logs/route.log"
    assert matches[0].line_number == 2


def test_bounded_excerpt_marks_truncation(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    excerpt = provider.read_excerpt(context, "reports/timing.rpt", max_bytes=8)
    assert excerpt.bytes_read == 8
    assert excerpt.truncated


def test_missing_artifact_is_named_error(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    with pytest.raises(ArtifactNotFoundError):
        provider.stat(context, "missing.rpt")


@pytest.mark.parametrize("path", ["../../outside", "/etc/passwd", "logs/../config.mk"])
def test_path_traversal_rejected(
    provider: LocalArtifactProvider, context: QueryContext, path: str
) -> None:
    with pytest.raises(ArtifactPathError):
        provider.stat(context, path)


def test_binary_metadata_is_available_but_read_is_rejected(
    provider: LocalArtifactProvider, context: QueryContext
) -> None:
    metadata = provider.stat(context, "results/final.odb")
    assert metadata.is_binary
    with pytest.raises(BinaryArtifactError):
        provider.read_excerpt(context, "results/final.odb")


def test_symlink_escape_rejected(
    provider: LocalArtifactProvider, context: QueryContext, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    assert context.workspace is not None
    link = context.workspace / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    try:
        with pytest.raises(ArtifactPathError):
            provider.stat(context, "escape.txt")
    finally:
        link.unlink()


def test_provider_exposes_no_write_or_shell_api(
    provider: LocalArtifactProvider,
) -> None:
    assert not hasattr(provider, "write")
    assert not hasattr(provider, "shell")

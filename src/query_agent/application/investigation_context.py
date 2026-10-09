"""Bounded model views; durable evidence remains complete and expandable."""

from __future__ import annotations

import json
from typing import cast

from query_agent.domain.evidence import Evidence, JsonValue
from query_agent.domain.investigation import OperationReceipt

SOURCE_METADATA = frozenset(
    (
        "artifact_id",
        "run_id",
        "attempt_id",
        "sha256",
        "logical_path",
        "category",
        "size_bytes",
        "stage",
        "format",
        "schema_version",
    )
)


def compact(value: JsonValue, *, depth: int = 0) -> JsonValue:
    """Keep explicit expansion markers; complete responses stay in state/evidence."""
    if isinstance(value, dict):
        if isinstance(value.get("artifact_id"), str) and isinstance(
            value.get("sha256"), str
        ):
            # An excerpt carries these identifiers too. Only deduplicate metadata;
            # preserve text, offsets, coverage and all other observation payloads.
            return {
                "source_ref": value["artifact_id"],
                **{
                    key: compact(item, depth=depth + 1)
                    for key, item in value.items()
                    if key not in SOURCE_METADATA
                },
            }
        if depth > 5:
            # Preserve observed scalar values at any nesting depth. A source
            # point's arrival/cell/pin must not disappear because it sits under
            # a fragment envelope; only nested detail is preview-limited.
            return {
                **{
                    key: item
                    for key, item in value.items()
                    if not isinstance(item, (dict, list))
                },
                "preview_omitted_nested_keys": [
                    key for key, item in value.items() if isinstance(item, (dict, list))
                ],
            }
        return {key: compact(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > 8:
            return {
                "items": [compact(item, depth=depth + 1) for item in value[:8]],
                "omitted_count": len(value) - 8,
                "preview_only": True,
                "original_item_count": len(value),
                "expand": (
                    "saved response contains every original item; "
                    "use evidence pagination"
                ),
            }
        return [compact(item, depth=depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 3072:
        return {
            "text": value[:3072],
            "omitted_characters": len(value) - 3072,
            "preview_only": True,
            "expand": "fetch next original source excerpt",
        }
    return value


def collect_sources(value: JsonValue, catalog: dict[str, JsonValue]) -> None:
    if isinstance(value, dict):
        key = value.get("artifact_id")
        if isinstance(key, str) and isinstance(value.get("sha256"), str):
            metadata = {
                name: item for name, item in value.items() if name in SOURCE_METADATA
            }
            # A later excerpt may contain fewer metadata fields than its reference.
            catalog[key] = {
                **cast(dict[str, JsonValue], catalog.get(key, {})),
                **metadata,
            }
        for item in value.values():
            collect_sources(item, catalog)
    elif isinstance(value, list):
        for item in value:
            collect_sources(item, catalog)


def scalar_first(value: JsonValue) -> JsonValue:
    """Place observed scalars before verbose nested details in preview text."""
    if isinstance(value, dict):
        return {
            key: scalar_first(item)
            for key, item in sorted(
                value.items(), key=lambda pair: isinstance(pair[1], (dict, list))
            )
        }
    if isinstance(value, list):
        return [scalar_first(item) for item in value]
    return value


def evidence_view(item: Evidence, limit: int) -> dict[str, JsonValue]:
    content = item.content
    if not isinstance(content, dict) or "original_evidence_id" not in content:
        content = compact(content)
    else:
        # Explicit saved-evidence pages must not be truncated a second time.
        limit = max(limit, len(json.dumps(content, ensure_ascii=False)))
    text = json.dumps(scalar_first(content), ensure_ascii=False)
    return {
        "evidence_id": item.evidence_id,
        "scope": cast(JsonValue, item.scope.model_dump(mode="json")),
        "status": item.status,
        "reason": item.reason,
        "locator": cast(JsonValue, item.locator.model_dump(mode="json")),
        "preview_truncated": has_omissions(content) or len(text) > limit,
        "expand": "/evidence/" + item.evidence_id + "/page",
        "content": content
        if len(text) <= limit
        else {
            "preview": text[:limit],
            "preview_truncated": True,
            "total_characters": len(text),
            "expand": "/evidence/" + item.evidence_id + "/page",
            "arguments": {"offset": "0", "max_characters": "6000"},
            "complete": False,
        },
    }


def has_omissions(value: JsonValue) -> bool:
    if isinstance(value, dict):
        if value.get("preview_only") or value.get("preview_omitted_nested_keys"):
            return True
        return any(has_omissions(item) for item in value.values())
    if isinstance(value, list):
        return any(has_omissions(item) for item in value)
    return False


def operation_views(items: list[OperationReceipt]) -> list[dict[str, JsonValue]]:
    return [
        {
            "operation_id": item.operation_id,
            "kind": item.kind,
            "path": item.request.get("path"),
            "status": item.status,
            "evidence_id": item.evidence_id,
            "run_id": item.run_id,
            "error": item.error,
        }
        for item in items
    ]

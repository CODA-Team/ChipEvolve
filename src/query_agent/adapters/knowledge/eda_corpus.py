"""Read-only lexical knowledge adapter for the EDA-Corpus CSV datasets."""

from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    JsonValue,
)
from query_agent.domain.query import QueryContext

_TOKEN = re.compile(r"[A-Za-z0-9_]+")
_QA_RELATIVE = Path("Non-Augmented_Data/Question-Answer/Question-Answer_Dataset.csv")
_FLOW_RELATIVE = Path("Non-Augmented_Data/Prompt-Script/Flow_Dataset.csv")


class EDACorpusKnowledgeProvider:
    """Search real EDA-Corpus QA and prompt-script rows without a vector store."""

    _provider_name = "eda-corpus-knowledge-provider"

    def __init__(self, corpus_root: str | Path, *, max_results: int = 5) -> None:
        root = Path(corpus_root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"EDA-Corpus root is not a directory: {root}")
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        self._root = root
        self._max_results = max_results
        self._datasets = self._load_datasets()

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.DOMAIN_KNOWLEDGE})

    def search(self, query: str, context: QueryContext) -> Sequence[Evidence]:
        """Return ranked rows whose prompt has lexical overlap with ``query``."""

        del context
        query_tokens = _tokens(query)
        if not query_tokens:
            raise ValueError("knowledge query must contain searchable terms")
        ranked = sorted(
            (
                (len(query_tokens & _tokens(row.prompt)), row)
                for row in self._datasets
                if query_tokens & _tokens(row.prompt)
            ),
            key=lambda item: (-item[0], item[1].dataset, item[1].row_number),
        )
        return tuple(
            row.to_evidence(self._provider_name)
            for _, row in ranked[: self._max_results]
        )

    def _load_datasets(self) -> tuple[_CorpusRow, ...]:
        rows: list[_CorpusRow] = []
        for dataset, relative, fields in (
            ("question-answer", _QA_RELATIVE, ("Prompts", "Answers")),
            ("prompt-script", _FLOW_RELATIVE, ("prompt", "code")),
        ):
            path = self._root / relative
            if not path.is_file():
                continue
            source_bytes = path.read_bytes()
            source_hash = hashlib.sha256(source_bytes).hexdigest()
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames is None or any(
                    field not in reader.fieldnames for field in fields
                ):
                    raise ValueError(f"unsupported {dataset} schema: {path}")
                for row_number, row in enumerate(reader, start=2):
                    prompt = (row.get(fields[0]) or "").strip()
                    answer = (row.get(fields[1]) or "").strip()
                    if prompt and answer:
                        rows.append(
                            _CorpusRow(
                                dataset=dataset,
                                relative_path=relative.as_posix(),
                                row_number=row_number,
                                prompt=prompt,
                                answer=answer,
                                source_hash=source_hash,
                                source_mtime=modified_at,
                            )
                        )
        if not rows:
            raise ValueError(
                f"no supported EDA-Corpus CSV datasets found under {self._root}"
            )
        return tuple(rows)


class _CorpusRow:
    def __init__(
        self,
        *,
        dataset: str,
        relative_path: str,
        row_number: int,
        prompt: str,
        answer: str,
        source_hash: str,
        source_mtime: datetime,
    ) -> None:
        self.dataset = dataset
        self.relative_path = relative_path
        self.row_number = row_number
        self.prompt = prompt
        self.answer = answer
        self.source_hash = source_hash
        self.source_mtime = source_mtime

    def to_evidence(self, provider: str) -> Evidence:
        locator = f"eda-corpus://{self.relative_path}#row={self.row_number}"
        content: dict[str, JsonValue] = {
            "dataset": self.dataset,
            "prompt": self.prompt,
            "answer": self.answer if self.dataset == "question-answer" else None,
            "script": self.answer if self.dataset == "prompt-script" else None,
            "row_number": self.row_number,
        }
        digest = hashlib.sha256(
            f"{self.source_hash}:{self.row_number}:{self.prompt}".encode()
        ).hexdigest()
        return Evidence(
            evidence_id=f"eda-{digest[:24]}",
            source_kind=EvidenceSourceKind.KNOWLEDGE,
            content=content,
            scope=EvidenceScope(),
            locator=EvidenceLocator(uri=locator),
            provenance=EvidenceProvenance(
                provider=provider,
                source_hash=self.source_hash,
                source_mtime=self.source_mtime,
                retrieved_at=datetime.now(UTC),
            ),
            fact_key=f"knowledge:{self.dataset}:{self.row_number}",
        )


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(value.lower()))

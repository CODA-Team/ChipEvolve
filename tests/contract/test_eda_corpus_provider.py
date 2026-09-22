from pathlib import Path

import pytest

from query_agent.adapters.knowledge import EDACorpusKnowledgeProvider
from query_agent.domain.query import QueryContext


def make_corpus(root: Path) -> Path:
    qa = root / "Non-Augmented_Data" / "Question-Answer"
    flow = root / "Non-Augmented_Data" / "Prompt-Script"
    qa.mkdir(parents=True)
    flow.mkdir(parents=True)
    (qa / "Question-Answer_Dataset.csv").write_text(
        "Prompts,Answers\n"
        'What is global routing?,"Global routing assigns routes on a grid."\n'
        'What is CTS?,"Clock tree synthesis distributes the clock."\n',
        encoding="utf-8",
    )
    (flow / "Flow_Dataset.csv").write_text(
        'code,prompt\n"global_route()","How do I run global routing?"\n',
        encoding="utf-8",
    )
    return root


def test_provider_returns_cited_qa_evidence(tmp_path: Path) -> None:
    provider = EDACorpusKnowledgeProvider(make_corpus(tmp_path))
    evidence = provider.search(
        "What is global routing?",
        QueryContext(workspace=tmp_path),
    )

    assert evidence
    item = evidence[0]
    assert isinstance(item.content, dict)
    assert item.content["prompt"] == "What is global routing?"
    assert item.content["answer"] == "Global routing assigns routes on a grid."
    assert item.locator.uri.endswith("Question-Answer_Dataset.csv#row=2")
    assert item.provenance.provider == "eda-corpus-knowledge-provider"
    assert item.provenance.source_hash is not None


def test_provider_includes_prompt_script_rows(tmp_path: Path) -> None:
    provider = EDACorpusKnowledgeProvider(make_corpus(tmp_path))
    evidence = provider.search(
        "How do I run global routing?",
        QueryContext(workspace=tmp_path),
    )

    assert any(
        isinstance(item.content, dict)
        and item.content.get("dataset") == "prompt-script"
        and item.content.get("script") == "global_route()"
        for item in evidence
    )


def test_provider_rejects_blank_query(tmp_path: Path) -> None:
    provider = EDACorpusKnowledgeProvider(make_corpus(tmp_path))

    with pytest.raises(ValueError, match="searchable terms"):
        provider.search("   ", QueryContext(workspace=tmp_path))


def test_provider_rejects_missing_dataset(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)

    with pytest.raises(ValueError, match="no supported"):
        EDACorpusKnowledgeProvider(tmp_path)

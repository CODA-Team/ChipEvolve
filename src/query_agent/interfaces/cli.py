"""Thin command-line composition and presentation boundary."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from query_agent.adapters.artifacts import LocalArtifactProvider
from query_agent.adapters.design_data import UnavailableDesignDataProvider
from query_agent.adapters.knowledge import EDACorpusKnowledgeProvider
from query_agent.adapters.run_evidence import (
    ExecutionFoundationExperimentContextProvider,
    ExecutionFoundationRunEvidenceAdapter,
    HttpExecutionFoundationClient,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.benchmark import BenchmarkRunner
from query_agent.domain.query import QueryContext, QueryRequest, QuerySource


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "benchmark":
        report = BenchmarkRunner().run(args.benchmark_dir)
        print(report.model_dump_json(indent=2))
        return 0 if report.failed == 0 else 1
    response = _service(args).query(
        QueryRequest(query=args.question, context=_context(args))
    )
    print(response.model_dump_json(indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="query-agent")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="ask an evidence-scoped question")
    ask.add_argument("question")
    ask.add_argument("--workspace", type=Path)
    ask.add_argument("--kernel-url")
    ask.add_argument("--token-env", default="QUERY_AGENT_KERNEL_TOKEN")
    ask.add_argument("--design")
    ask.add_argument("--run")
    ask.add_argument("--stage")
    ask.add_argument(
        "--eda-corpus",
        type=Path,
        help="optional local EDA-Corpus checkout used for knowledge queries",
    )
    benchmark = commands.add_parser("benchmark", help="run deterministic cases")
    benchmark.add_argument("benchmark_dir", type=Path)
    return parser


def _context(args: argparse.Namespace) -> QueryContext:
    if args.kernel_url:
        return QueryContext(
            design_id=args.design,
            run_id=args.run,
            stage=args.stage,
            source=QuerySource.MANAGED_RUN,
        )
    return QueryContext(
        workspace=args.workspace,
        design_id=args.design,
        run_id=args.run,
        stage=args.stage,
        source=QuerySource.LOCAL_WORKSPACE,
    )


def _service(args: argparse.Namespace) -> QueryService:
    knowledge_provider = (
        EDACorpusKnowledgeProvider(args.eda_corpus, max_results=1)
        if args.eda_corpus is not None
        else None
    )
    if args.kernel_url:
        client = HttpExecutionFoundationClient(
            args.kernel_url,
            token=os.environ.get(args.token_env),
        )
        collector = EvidenceCollector(
            run_evidence_provider=ExecutionFoundationRunEvidenceAdapter(client),
            experiment_context_provider=ExecutionFoundationExperimentContextProvider(
                client
            ),
            design_data_provider=UnavailableDesignDataProvider(),
            knowledge_provider=knowledge_provider,
        )
    else:
        if args.workspace is None:
            raise SystemExit("ask requires either --workspace or --kernel-url")
        collector = EvidenceCollector(
            artifact_provider=LocalArtifactProvider(args.workspace),
            design_data_provider=UnavailableDesignDataProvider(),
            knowledge_provider=knowledge_provider,
        )
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=collector,
        experiment_context_provider=collector.experiment_context_provider,
    )


if __name__ == "__main__":
    sys.exit(main())

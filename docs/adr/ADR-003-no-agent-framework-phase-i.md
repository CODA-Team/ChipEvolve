# ADR-003: No Agent Framework in Phase I

## Context

Phase I needs a stable, testable foundation, not orchestration complexity.

## Decision

Use an ordinary Python service for parse, plan, collect, evaluate and respond.
Do not add LangGraph, AutoGen, CrewAI, or another multi-agent framework.

## Consequences

Control flow is visible and deterministic. A later workflow can be introduced
at an explicit boundary without making framework state part of the domain.

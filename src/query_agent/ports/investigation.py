"""Investigation effects and persistence are explicit replaceable ports."""

from typing import Protocol

from query_agent.domain.evidence import Evidence
from query_agent.domain.investigation import (
    AnalysisRequest,
    AnalysisTicket,
    FixedScope,
    InvestigationState,
    ReadOperation,
    SkillRecord,
)
from query_agent.ports.llm import LanguageModel


class InvestigationDataPort(Protocol):
    def set_timeout(self, seconds: float) -> None: ...
    def resolve_scope(self, snapshot_id: str, role: str) -> FixedScope: ...
    def read(self, operation: ReadOperation, scopes: list[FixedScope]) -> Evidence: ...


class InvestigationAnalysisPort(Protocol):
    def set_timeout(self, seconds: float) -> None: ...
    def submit(
        self, request: AnalysisRequest, scopes: list[FixedScope]
    ) -> AnalysisTicket: ...
    def poll(
        self, ticket: AnalysisTicket
    ) -> tuple[AnalysisTicket, FixedScope | None]: ...
    def cancel(self, ticket: AnalysisTicket) -> AnalysisTicket: ...


class InvestigationStore(Protocol):
    def load(self, investigation_id: str) -> InvestigationState: ...
    def save(self, state: InvestigationState, expected_revision: int) -> None: ...


class SkillProvider(Protocol):
    def load(self, names: list[str]) -> list[SkillRecord]: ...


class InvestigationModel(LanguageModel, Protocol):
    def set_timeout(self, seconds: float) -> None: ...

"""CLI-independent commands and immutable normalization of business requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chip_evolve.core.contracts import (
    BusinessInputError,
    Capability,
    FlowRecipe,
    JSONValue,
    Operation,
    QualifiedEnvironmentRef,
    SearchBudget,
    SpecialistRequest,
)


def positive(value: int | None, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BusinessInputError(
            "invalid_budget", "$." + field, "positive integer required"
        )
    return value


@dataclass(frozen=True)
class RunCommand:
    config: Path
    design: str
    key: str
    capability: Capability
    source: Path | None = None
    objective: Path | None = None
    context: Path | None = None
    code_source: Path | None = None
    seconds: int | None = None
    rounds: int | None = None
    candidates: int | None = None
    flow_recipe: FlowRecipe | None = None
    environment: Path | None = None
    operation: Operation = "evolve"

    def normalized(
        self, default_environment: Path | None = None
    ) -> NormalizedRunCommand:
        if self.capability not in {"orfs", "flow", "dpl", "goal", "eco"}:
            raise BusinessInputError(
                "invalid_capability", "$.capability", "unknown specialist"
            )
        if (
            not self.design
            or Path(self.key).name != self.key
            or self.key in {".", "..", ""}
        ):
            raise BusinessInputError(
                "invalid_identifier", "$.key", "one experiment directory name required"
            )
        recipe = self.flow_recipe or (
            "source" if self.capability == "flow" else "legacy"
        )
        if recipe not in {"legacy", "source"} or (
            recipe != "legacy" and self.capability != "flow"
        ):
            raise BusinessInputError(
                "invalid_mode",
                "$.flow_recipe",
                "--flow-recipe source applies to Flow only",
            )
        if self.operation not in {"evolve", "replay", "framework"}:
            raise BusinessInputError("invalid_mode", "$.operation", "unknown operation")
        if self.operation == "framework" and self.capability != "dpl":
            raise BusinessInputError(
                "invalid_mode",
                "$.operation",
                "--operation framework selects the original DPL framework only",
            )
        if self.capability == "orfs" and bool(self.source) != (
            self.operation == "replay"
        ):
            raise BusinessInputError(
                "invalid_mode",
                "$.source",
                "ORFS source handoff requires --operation replay and --source together",
            )
        if self.code_source and (
            self.capability not in {"dpl", "goal"} or self.operation != "replay"
        ):
            raise BusinessInputError(
                "invalid_mode",
                "$.code_source",
                "--code-source requires DPL or Goal --operation replay",
            )
        if self.candidates is not None and self.capability not in {"flow", "dpl"}:
            raise BusinessInputError(
                "invalid_mode",
                "$.candidates",
                "--candidates applies to Flow/DPL; Goal keeps four Students",
            )
        seconds = positive(
            self.seconds
            if self.seconds is not None
            else (10800 if self.capability in {"flow", "dpl", "goal"} else 5400),
            "seconds",
        )
        rounds = positive(
            self.rounds
            if self.rounds is not None
            else (2 if self.capability == "flow" else 1),
            "rounds",
        )
        candidates = (
            self.candidates
            if self.candidates is not None
            else {"flow": 12, "dpl": 3, "goal": 4}.get(self.capability)
        )
        if candidates is not None:
            positive(candidates, "candidates")
        environment = self.environment or default_environment
        return NormalizedRunCommand(
            config=self.config,
            design=self.design,
            key=self.key,
            capability=self.capability,
            source=self.source,
            context=self.context,
            code_source=self.code_source,
            operation=self.operation,
            seconds=seconds,
            rounds=rounds,
            candidates=candidates,
            flow_recipe=recipe,
            objective=self.objective.resolve() if self.objective else None,
            environment=environment.resolve() if environment else None,
        )

    def specialist(
        self, environment: QualifiedEnvironmentRef | None = None
    ) -> SpecialistRequest:
        if self.capability == "orfs":
            raise BusinessInputError(
                "invalid_capability", "$.capability", "baseline is not a specialist"
            )
        if self.flow_recipe is None:
            raise BusinessInputError(
                "invalid_state", "$.flow_recipe", "normalize the run before dispatch"
            )
        return SpecialistRequest(
            self.design,
            self.key,
            self.capability,
            self.operation,
            SearchBudget(
                positive(self.seconds, "seconds"),
                positive(self.rounds, "rounds"),
                self.candidates,
            ),
            self.code_source,
            self.flow_recipe,
            environment,
        )

    def to_wire(self) -> dict[str, JSONValue]:
        """Original flat request keys, including explicit nulls and CLI identity."""
        return {
            "config": str(self.config),
            "command": "run",
            "design": self.design,
            "capability": self.capability,
            "key": self.key,
            "source": str(self.source.resolve()) if self.source else None,
            "objective": str(self.objective) if self.objective else None,
            "context": str(self.context) if self.context else None,
            "code_source": str(self.code_source) if self.code_source else None,
            "seconds": self.seconds,
            "rounds": self.rounds,
            "candidates": self.candidates,
            "flow_recipe": self.flow_recipe,
            "environment": str(self.environment) if self.environment else None,
            "operation": self.operation,
        }


@dataclass(frozen=True)
class NormalizedRunCommand(RunCommand):
    """A run with immutable, explicit defaults; never re-normalize saved requests."""

    seconds: int = 5400
    rounds: int = 1
    flow_recipe: FlowRecipe = "legacy"


@dataclass(frozen=True)
class ResultCommand:
    result: Path


@dataclass(frozen=True)
class CompareCommand:
    result: Path
    against: Path


@dataclass(frozen=True)
class ValidateCommand(CompareCommand):
    key: str


@dataclass(frozen=True)
class SelectCommand(ResultCommand):
    reason: str
    validation: Path


@dataclass(frozen=True)
class DesignCommand:
    design: str


@dataclass(frozen=True)
class ResumeCommand(DesignCommand):
    key: str


@dataclass(frozen=True)
class WatchCommand(DesignCommand):
    run_id: str


@dataclass(frozen=True)
class DiagnoseCommand(ResultCommand):
    question: str
    seconds: int = 600
    steps: int = 6
    against: Path | None = None
    analyses: int = 0


@dataclass(frozen=True)
class CandidateFactsCommand:
    reference: Path
    result: tuple[Path, ...]
    key: str


@dataclass(frozen=True)
class ContinueGoalCommand(ResultCommand):
    context: Path
    key: str
    seconds: int = 21600

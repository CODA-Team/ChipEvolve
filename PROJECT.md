# Project scope

ChipEvolve provides the physical-design capabilities Codex uses as the paper's Control Agent. Codex receives the design goal, checks actual evidence, selects a specialist and its budget, and evaluates the returned candidate against the same design conditions.

The first release includes the Analysis Agent (`query-agent`), Flow Agent, DPLEvolve, GoalEvolve, and TimingECOAgent, with the execution, data, SDK, and native tool modules they depend on. Each specialist retains its upstream algorithms, provenance, and license. Shared orchestration uses the existing experiment and snapshot contracts.

The engineering target is a fresh local install and a small, traceable GCD experiment. Public acceptance also depends on every pinned source revision and the qualified toolchain being obtainable by an external user. See [Architecture](ARCHITECTURE.md) and [Engineering status](TASKS.md).

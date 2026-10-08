# Development discipline

Use this project's .venv and `python3 ../dev.py data-interface check`.
Cross-project dependencies use released wheels/public HTTP; no sibling editable or PYTHONPATH.
Tests use temporary state. Keep transport separate from data ownership; preserve named errors,
ambiguity and missing evidence. Document breaking changes and increment the contract.
Release through ../admin/build_wheels.py; record wheel hashes and installed lock files.
Real OpenROAD and capable direct-Codex comparisons belong in the workspace acceptance report.
Synthetic mechanism tests must not be presented as real design or AI performance.

# Contributing

This repository owns generic single-machine execution contracts, lifecycle, input/artifact containment, process/resource accounting and provenance. Tool-specific algorithms and EDA semantics belong in external plugins. Accounts, UI and plan orchestration were retired in 0.2.

`tools/install-local.sh` creates the repository environment and installs only its own packages. Cross-project dependencies use released wheels or HTTP. Read AGENTS.md, preserve G1–G17 and their negative fixtures, keep every production commit within one architecture layer, and never raise a size ceiling as a shortcut.

Run `python3 ../dev.py execution-foundation check`, source mypy, changed-file Ruff/Black and `git diff --check`. Tests use temporary state; real EDA acceptance is a separate command and report under the workspace admin/benchmarks directory. Synthetic/fake tool tests prove mechanisms, never EDA performance. Every claimed advantage needs paired comparison with a capable direct-terminal baseline.

The service starts with `tools/start-platform.sh`, binds loopback, and includes one worker. A plugin follows docs/PLUGIN_PROTOCOL.agent.md, receives an immutable task, declares artifacts, and returns metrics tied to source bytes. Runtime supplies EXECUTION_RUN_ID, EXECUTION_ATTEMPT_ID and EXECUTION_TASK_ID after the caller's environment; producers may use these for data ownership. An analysis run describes another run only through explicit parent lineage.

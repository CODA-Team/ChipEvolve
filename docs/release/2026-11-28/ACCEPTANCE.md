# Accepted backend cleanup, 2026-11-28

This record describes owner-accepted Slice 1/2/3/4A/4B/4C outcomes and their actual limits. Slice 3.5 stopped after default fixes and test/support migration; 4A repaired the migration defects. Slice 4D is approved, but its profile/resource consolidation, four-package source moves and 377 historical moves have not started. TUI and Web remain frozen.

The root package currently contains 49 implementation modules. Goal/ECO/Flow delivery have explicit owners, typed boundaries and staged orchestration; the current source is still physically flat. Codex is the Control Agent. The nine Git modules are five specialist Agents plus four infrastructure modules; Data Interface is an SDK.

The final 4C root check passed 1,310 cases, preserving the previous 1,260 and adding 50. The recorded whole-depth AST graph has zero cycles, upward imports and private cross-module calls. Five strict Pyright files and an 18-file basic call chain have zero errors; seven intentional bad callers produce the expected diagnostics. These are bounded checks, not whole-repository strict typing or a proof of all behavior.

Real GCD/Nangate45 evidence covers the fixed 500 ps baseline, one legal ECO no-op, comparison, 18/18 output proof, exact independent physical replay, SDK identities, adoption and completed recovery. No PPA improvement is claimed. The 4C run downloaded and checked 114 new artifacts, preserved its run ID and 139 experiment JSON files on resume, and left its 1,170 original input-state files unchanged. Its isolated services were stopped.

Real Code evolution additional delivery, complete Flow success/failure collector acceptance and some historical Goal recovery material remain pending. Three archived Flow configs were recovered with their real hashes, which is not full collector acceptance. Synthetic tests or an ECO no-op do not close these gaps.

Packaging has 11 platform wheels from five Git projects (seven EF components and one each from Toolkits/DF/DI/Query). Flow/DPL/Goal/ECO still use their own frozen source and installed public wheel dependencies. Ten environments do not mean ten distributable packages, and pip's no-editable result does not prove the whole application can run with source removed.

Result validity, constraint feasibility, independent validation and adoption remain separate. Finite but over-limit results remain evidence; corrupted metrics are rejected. Specialist internal promotion never automatically becomes platform adoption.

The independent publication candidate rebuilt 11 wheels from the nine unchanged public pins, installed ten separate environments, and passed a fresh 1,310-case root check, whole-depth architecture checks, strict/core typing and the seven expected negative diagnostics. Root and all 13 subcommand help outputs match the accepted workspace. The published static logs are these fresh checks; the runtime evidence above is explicitly reused from qualified Slice 4C receipts. Remote completion is established separately by the actual delivery Commit and a matching remote branch HEAD.

- [Validation scope](validation-summary.json)
- [Recorded root check](root-check.log) (workspace path redacted; original SHA retained)
- [Type diagnostics](pyright-checks.json)
- [Architecture graph](architecture.json)
- [Traceability](traceability.json)

Reproduce the static calls with the bootstrap-installed `agent/query-agent/.venv/bin/pyright --project docs/release/2026-11-28/checks/strict.json` and `core.json`. The `negative.json` check must exit 1 with the seven expected errors. These configs use the installed root environment and contain no machine-specific absolute path.

The software in this backfill is recorded by Commit `e99c33b53a689c2c83aa29af349b20b034ab4d21`. Its engineering gates passed before committing. The authorized remote target is `CODA-Team/ChipEvolve:engineering/cleanup-b6cfd1d`; remote equality is verified after push in the delivery report.


This is the historical backfill scope. Current four-package/profile work is
recorded in the [Slice 4D report](../2026-11-29/SLICE4D_REPORT.md). The shared
reproduction configs now follow canonical paths (7 strict / 20 core files);
the historical 5/18-file logs above remain unchanged evidence of that delivery.

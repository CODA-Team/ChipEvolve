# Engineering status

The release candidate starts from `b6cfd1d`. Its nine modules are fixed by the
root gitlinks and [source manifest](SOURCE_MANIFEST.json). The local
`engineering/baseline-b6cfd1d` tag retains the original engineering baseline.
Use the [quickstart](README.md) to install the candidate and the
[dispatch table](agent/README.md) to choose a specialist.

## Release checks

| Area | Evidence |
|---|---|
| Source and environment | A fresh GitHub checkout of `e5dbcac` verified all nine module revisions and trees, rebuilt 11 wheels, and installed ten separate Python environments. With the same module pins and environments, the public `7829863` revision passed 2,564 tests with one host-dependent skip in `python3 dev.py all check`. |
| Rocky Linux x86_64 | The same checkout ran GCD through ORFS and OpenROAD with a four-core, 12 GiB stack. The routed result had zero DRC violations. The SDK resolved the three fact views to `run-63fae3749035403b90cac10fb909f616` and found the original EF artifacts. Recovery returned the same run ID. |
| openEuler 24.03 x86_64 | A fresh GitHub checkout of `874b666` installed all ten environments in openEuler and used its Apptainer package `1.1.6-2.oe2403`. GCD delivered three fact views and registered artifacts with zero route DRC. Slack matched Rocky, and recovery returned `run-7a7d37837c794f9aaf941001df9b9dea`. This check used rootless Podman in privileged container mode for Apptainer's nested mounts. |
| Linux ARM64 | A fresh GitHub checkout of `2d622f3` on native ARM64 installed all ten environments and repackaged the cached native ORFS build with KLayout 0.30.12 discoverable on PATH. GCD completed through GDS. It delivered three fact views and registered EF artifacts with zero route DRC. Recovery returned `run-25e9ba43c0c54a1a8a5e2e1ba1c155bf`. [Run](https://github.com/CODA-Team/ChipEvolve/actions/runs/44749175211) · [Receipts](https://github.com/CODA-Team/ChipEvolve/actions/runs/44749175211/artifacts/14634877326) |
| Licensing | The root project and Data Interface use MIT. TimingECOAgent is in the first release, with its upstream attribution in its [NOTICE](agent/timing-eco-agent/NOTICE). The maintainer confirmed redistribution permission. Its written record is pending. |

## Specialist checks on GCD

| Specialist | Measured behavior |
|---|---|
| Query Agent | Requested a bounded new timing analysis through EF, imported its facts, and cited the new setup/hold path. The SDK also returned the exact SPEF record bytes for a routed net, verified against the registered artifact. |
| Flow Agent | Two native rounds made 17 successful model calls. The second round used first-round evidence. All six delivered candidates had zero route DRC violations and four met the configured constraints. After a shared host lock delayed one measurement, two recovery calls reused the search and returned the same six run IDs. |
| DPLEvolve | Built a public-source core and verified 89 native algorithm files. A live Teacher assigned one Student, reviewed the measured proposal, and the native selection accepted source commit `e60cc1d`. The placement hash matched the CTS and routing inputs. The SDK resolved all three fact views for `run-c4b75d301f604ac6b6687629b124b30c`, which had zero route DRC and retained its ID on recovery. A separate saved-patch replay delivered `run-f27a93761df344febbb195b93c8d33e9`. |
| GoalEvolve | Compiled the public source through EF and passed all four official structural checks on GCD. After the first budget expired, the native CLI reused the Teacher plan and four Student sessions. All four candidates completed physical evaluation. The native verdicts refuted their hypotheses, and the original parent was retained. Platform recovery reused the completed round. The selected baseline and all four candidates were remeasured with their own EF producers. The retained baseline delivered three fact views, zero route DRC, and the same ID on a second recovery, `run-7865578b0df74cbbb0bfe5c73b1305d2`. |
| TimingECOAgent | Ran a two-round native session at 400 ps with four cores and recovered the same delivery ID. Common physical validation rerouted the selected checkpoint to zero DRC. In a separate EF-supervised action check, inserting a `BUF_X2` connected the selected load through it, and removing the buffer restored the original topology. |

The GCD runs cover the platform handoffs and the specialist paths listed above.
Paper-scale search and statistical results have separate protocols and
records. [Earlier local GCD acceptance](archive/records/A111_GCD_SPECIALIST_ACCEPTANCE_20261120.md)

## Handoff review follow-up

Specialist dispatch checks the EF-registered identity of the actual files or
artifact IDs it supplies. Unfinished recovery verifies the requested runtime
and qualified environment. Goal resolves copied checkpoints from native
Student and stage baseline receipts and rejects ambiguous producers. Controller
snapshots preserve working-tree deletions and renames. Native ORFS Make paths
are checked before dispatch.

A fresh GitHub checkout of `ba80e93` with the follow-up patch rebuilt 11 wheels
and installed ten Python environments. `python3 dev.py all check` passed
2,569 tests with one host-dependent skip. OSV returned no matches for the 66
release dependency pins after the Black and setuptools updates.

An isolated GCD/Nangate45 run at 400 ps delivered an ORFS baseline, a cited
Query diagnosis, and one native Timing ECO round. The first Query attempt
timed out at 240 seconds. A narrower prompt succeeded on retry. The delivered
result `run-092d8d817a474678b988d99149f1f0db` had zero route DRC, resolved
all three fact views through the SDK, and kept its ID on recovery. The SDK
downloaded the three ECO input artifacts and their hashes matched the handoff
receipt. Separate checks using the live EF records rejected changed Goal and
Flow input files, a changed DPL archive, a changed ECO artifact receipt, and a
replaced image for unfinished recovery. Flow, DPL and Goal full-search
acceptance is recorded in the specialist table above.

For the ARM64 build history, the initial Bazel run failed a Slang archive
checksum. The CMake build used the same pinned Slang Git commit. The next
GCD run reached GDS and showed that the compiled KLayout executable was
outside PATH. The final run reused the saved native build and verified the
packaged runtime. [Initial build](https://github.com/CODA-Team/ChipEvolve/actions/runs/44697993963) · [GDS failure log](https://github.com/CODA-Team/ChipEvolve/actions/runs/44730556430)

## Release cleanup slices

The owner accepted Slice 1 on 2026-11-28. It rejects missing, non-numeric and
non-finite final metrics and makes result comparison depend on adoption rules
in one direction. Its root check passed 1,147 tests.

Slice 2 moves fact publication, source preparation, physical continuation and
business recovery to their [declared layers](ARCHITECTURE.md#root-package-layers).
The complete 42-module root graph has zero cyclic import groups and zero upward
layer imports. Both counts include function-local imports. Four lower-level or
orchestration owners were added to the previous 38 modules. The root CLI and all
13 subcommand help outputs match the Slice 1 baseline.

`python3 dev.py root check` now includes root code formatting alongside lint,
dependency consistency and pytest. It passed 1,151 tests after the Slice 2
changes. The existing regression assertions were retained while test bindings
followed the relocated functions. The [admin file catalog](admin/FILE_CATALOG.csv)
identifies 12 public install/runtime files, two guide files, 98 root test files,
50 test-support files and 394 historical files, with consumers and proposed
destinations.

The owner accepted Slice 2 and the isolated Slice 3 installation/EDA checks.
Slice 3.5 is paused after default configuration fixes and test/support migration;
root package migration and historical archiving remain unfinished. Slice 4A's
path repairs passed 1,168 root tests and have been accepted by the owner.

Slice 4B implements the approved business types, strict loading boundaries,
CLI-independent requests and common specialist Protocol. Its engineering receipts
are under `var/release/slice4b-20261128/`; the owner has accepted and closed
Slice 4B. Its four new modules brought the root graph to 46 implementation modules.
Type diagnostics, zero-submission negative cases, wire/SHA compatibility,
architecture checks and the complete root regression are separate gates. A new
isolated GCD instance checks the changed runtime seams using the already
qualified image and pinned module installations.

The local Query and Data Foundation checkouts retain their previously reported
pin differences and user changes. Slice 4B does not change their source or the
source manifest.

Slice 4C implements the approved responsibility and public-boundary cleanup.
`goal.py`, `eco.py` and `flow_delivery.py` bring the root graph to 49 modules;
`native.py` retains six explicit public aliases. Code evidence has three typed
public interfaces, and the three orchestration entry points expose their input,
execution and delivery stages. Whole-package AST gates cover private access,
cyclic imports, upward imports and CLI isolation. The root check passes 1,310
tests. Pyright checks five strict contract/caller files and an 18-file basic
call chain with zero errors; seven intentional protocol errors are diagnosed.

The short real ECO check uses an independent copy of the stopped Slice 4B
EF/DF state and the original immutable baseline/context. It does not start the
old services or repeat the search. Its result is a no-op, with no claimed PPA
gain. Three archived A111 Flow configurations match their recorded SHA256,
but this alone does not qualify the new collector. Complete Code evolution
packages and Flow success/failure collector runtime acceptance remain pending
where the historical materials are unavailable or not qualified. The complete
gate status and limitations are in
`var/release/slice4c-20261128/SLICE4C_REPORT.md`.

The owner has accepted and closed Slice 4C, including the documented limits of
its G6 evidence. Slice 4D is approved for implementation, with the initial Git
synchronization audit and confirmed backfill preceding source work. TUI and Web
remain frozen. Engineering, business acceptance and remote delivery are tracked
separately in the [release scope](docs/release/2026-11-28/ACCEPTANCE.md).


## Slice 4D implementation (pending business acceptance)

First synchronization delivered `e99c33b` and `4c8bccd` to the authorized
engineering branch. The original user workspace and module modifications remain
untouched. Slice 4D works from that clean delivery with the same nine public pins.

Steps 1–2 add the integration profile and named resource/admission owners.
Steps 3–4 move 51 implementations into four packages with one-object legacy
compatibility, and archive 377 files with their original SHA256. Seventeen
unaccepted local files stay at their original paths outside the delivery.
The recursive physical graph, original logical layers, private boundaries and
CLI/driver compatibility are checked. Static/root checks, zero-edit GCD runtime
checks and final Git delivery have separate receipts; none implies owner acceptance.

The isolated default GCD closure, Flow switch separation and final delivery are
tracked in the Slice 4D report. Complete real Code additional delivery, Flow
collector and some historical Goal recovery evidence remain inherited gaps.
No new long Code build or model search is authorized here. TUI/Web remain frozen
until the owner accepts the backend prerequisites.


Slice 4D engineering evidence: [report](docs/release/2026-11-29/SLICE4D_REPORT.md).
The root gate passed 1,347 tests; default GCD proof, replay, adoption and
completed recovery passed. Owner business acceptance and Git delivery remain
separate; TUI/Web remain frozen.

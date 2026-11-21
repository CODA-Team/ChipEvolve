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
records. [Earlier local GCD acceptance](admin/A111_GCD_SPECIALIST_ACCEPTANCE_20261120.md)

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

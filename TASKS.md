# Engineering status

The candidate starts at `b6cfd1d` and includes TimingECOAgent. The baseline tag `engineering/baseline-b6cfd1d` retains the previous document and source history. The reports under `admin/` record earlier paper experiments and their conditions.

| Priority | Work | Acceptance |
|---|---|---|
| P0 | Protect source, design inputs, histories, and toolchain. Reset owned historical experiment state. | The baseline and original uncommitted work are preserved. The engineering candidate resolves all nine gitlinks locally. |
| P1 | Install a fresh GCD stack and verify the shortest real flow. | A fresh Python install ran ORFS and OpenROAD at a 500 ps clock. EF registered artifacts, DF imported the three fact views, and the SDK resolved them to the measured run. `resume` returned the original run identity. |
| P2 | Separate CLI, specialist delivery, and tool parsing. | The root regression suite passed 781 tests. Data Foundation passed 385 tests, including the public Toolkit queries. A real Query → Timing ECO → EF → DF → Query handoff preserved the baseline checkpoint and returned equivalent reported timing. EF registered two ECO model receipts. |
| P3 | Qualify a public release. | The candidate branch and all nine module pins are publicly accessible. The workspace and Data Interface use MIT. Verify the remaining specialist workflows and native ARM64 execution before publishing the candidate as the default branch. |

GCD is a small workflow check. The smoke result had setup and hold worst slack of 39.032 ps and 110.505 ps respectively, with zero TNS in both checks. Its one-round ECO session kept the original routed checkpoint. Paper-scale search and statistical results have their own experimental protocols and records.

The A111 local run used fresh Python environments and newly generated GCD inputs. Flow ran one native round with three delivered candidates. DPLEvolve ran its native framework and handed off placement to CTS and routing. GoalEvolve replayed its native baseline with the prepared binary, ran the four structural checks, and delivered a routed and measured result. The nine-module and root check passed 2,562 tests with one host-dependent skip. The release checklist still needs public checkout acceptance and clean build and search evidence for DPL and Goal. [A111 acceptance record](admin/A111_GCD_SPECIALIST_ACCEPTANCE_20261120.md)

On Rocky Linux x86_64, a fresh GitHub clone of `7e6f514` installed ten Python environments and ran GCD with the pinned public ORFS image. The SDK resolved all three fact snapshots and the physical run's registered artifacts. `resume` returned the original run ID. Query used the same installed environment to collect and cite a new setup/hold timing supplement. The 400 ps ECO case executed a native round and delivered the retained checkpoint after it found no improvement.

An isolated openEuler 24.03 x86_64 container also installed the ten Python environments and delivered the three GCD fact snapshots with matching reported slack. That run used the host's Apptainer runtime and compatibility libraries mounted in the container.

The first native ARM64 run installed the Python environments and stopped during OpenROAD build at a Slang archive checksum mismatch. The retry uses the same Slang commit from OpenROAD's pinned Git submodule through CMake. The workflow still needs to finish the build and run physical GCD. [First run](https://github.com/CODA-Team/ChipEvolve/actions/runs/44697993963) · [Retry](https://github.com/CODA-Team/ChipEvolve/actions/runs/44710532602)

A fresh GitHub checkout of `33286ef` verified nine commit and tree pins, built 11 wheels, and installed ten virtual environments using the already downloaded third-party wheels. `python3 dev.py all check` passed 2,556 tests and reported one skip. GoalEvolve's 458 platform unit tests ran without the paper archive. Its frozen AST and official AES checker also passed in a full GoalEvolve checkout.

The same installation ran the `3906ab1` GCD entry point with four CPU cores and 12 GiB of stack capacity. The SDK resolved the three fact snapshots to measurement run `run-4eea0936c5dc43d8927df7a51b7b9958` and listed the source physical run's artifacts. Route DRC was zero and `resume` returned the original run ID. An EF-supervised check of Timing ECO's `BUF_X2` primitive connected the selected load through the buffer, then removed it and verified that the original topology was restored.

Flow ran two native GCD rounds with 17 successful model calls, used first-round evidence in the second round, and delivered six routed candidates. All six had zero route DRC errors and four met the configured final constraints. A common measurement initially timed out behind a separate build sharing the host lease. After isolating the lease and starting a new measurement within the same candidate collection, two `resume` calls returned the same six run IDs. The search receipts were reused.

DPLEvolve's first live round exposed a 10-thread default on an 8-core stack. The launch now uses the deployment budget. A separate cold build produced the common core and a receipt for 89 matching algorithm files. EF also rebuilt a preserved Student patch with that core. DPL measured the patch's placement, handed the same placement hash to CTS and routing, and delivered three fact snapshots with zero route DRC under `run-f27a93761df344febbb195b93c8d33e9`. A separate one-Student round checks generation and measurement together.

On a 4-core stack, Timing ECO ran a native session at a 400 ps clock. Common physical validation reused its registered checkpoint and rerouted it. The native checkpoint reported 43 route violations and the delivered result had zero. A separate two-round session completed with the same four-core budget and recovered its original delivery ID. The SDK also read the source SPEF record of a routed GCD net and matched its exact byte range against the registered artifact.

The GitHub checkout of `9df61d2` passed 2,559 tests with one skip. The subsequent common physical budget change passed all 784 root tests. GoalEvolve's public source built through EF and passed the official four structural checks on GCD. Its native Teacher assigned four Students and the search remains under qualification.

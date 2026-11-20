# Engineering status

The candidate starts at `b6cfd1d` and includes TimingECOAgent. The baseline tag `engineering/baseline-b6cfd1d` retains the previous document and source history. The reports under `admin/` record earlier paper experiments and their conditions.

| Priority | Work | Acceptance |
|---|---|---|
| P0 | Protect source, design inputs, histories, and toolchain. Reset owned historical experiment state. | The baseline and original uncommitted work are preserved. The engineering candidate resolves all nine gitlinks locally. |
| P1 | Install a fresh GCD stack and verify the shortest real flow. | A fresh Python install ran ORFS and OpenROAD at a 500 ps clock. EF registered artifacts, DF imported the three fact views, and the SDK resolved them to the measured run. `resume` returned the original run identity. |
| P2 | Separate CLI, specialist delivery, and tool parsing. | The root regression suite passed 771 tests. The affected DF tests passed 85 tests. A real Query → Timing ECO → EF → DF → Query handoff preserved the baseline checkpoint and returned equivalent reported timing. EF registered two ECO model receipts. |
| P3 | Qualify a public release. | The candidate branch and all nine module pins are publicly accessible. The workspace and Data Interface use MIT. Verify the remaining specialist workflows and native ARM64 execution before publishing the candidate as the default branch. |

GCD is a small workflow check. The smoke result had setup and hold worst slack of 39.032 ps and 110.505 ps respectively, with zero TNS in both checks. Its one-round ECO session kept the original routed checkpoint. Paper-scale search and statistical results have their own experimental protocols and records.

The A111 local run used fresh Python environments and newly generated GCD inputs. Flow ran one native round with three delivered candidates. DPLEvolve ran its native framework and handed off placement to CTS and routing. GoalEvolve replayed its native baseline with the prepared binary, ran the four structural checks, and delivered a routed and measured result. The nine-module and root check passed 2,562 tests with one host-dependent skip. The release checklist still needs public checkout acceptance and clean build and search evidence for DPL and Goal. [A111 acceptance record](admin/A111_GCD_SPECIALIST_ACCEPTANCE_20261120.md)

On Rocky Linux x86_64, a fresh GitHub clone of `7e6f514` installed ten Python environments and ran GCD with the pinned public ORFS image. The SDK resolved all three fact snapshots and the physical run's registered artifacts. `resume` returned the original run ID. Query used the same installed environment to collect and cite a new setup/hold timing supplement. The 400 ps ECO case executed a native round and delivered the retained checkpoint after it found no improvement.

An isolated openEuler 24.03 x86_64 container also installed the ten Python environments and delivered the three GCD fact snapshots with matching reported slack. That run used the host's Apptainer runtime and compatibility libraries mounted in the container. The native ARM64 GitHub Actions run has its own build and execution checks. [ARM64 workflow](https://github.com/CODA-Team/ChipEvolve/actions/workflows/arm-gcd.yml)

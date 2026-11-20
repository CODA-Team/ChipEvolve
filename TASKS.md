# Engineering status

The candidate starts at `b6cfd1d` and includes TimingECOAgent. The baseline tag `engineering/baseline-b6cfd1d` retains the previous document and source history. The reports under `admin/` record earlier paper experiments and their conditions.

| Priority | Work | Acceptance |
|---|---|---|
| P0 | Protect source, design inputs, histories, and toolchain. Reset owned historical experiment state. | The baseline and original uncommitted work are preserved. The engineering candidate resolves all nine gitlinks locally. |
| P1 | Install a fresh GCD stack and verify the shortest real flow. | A fresh Python install ran ORFS and OpenROAD at a 500 ps clock. EF registered artifacts, DF imported the three fact views, and the SDK resolved them to the measured run. `resume` returned the original run identity. |
| P2 | Separate CLI, specialist delivery, and tool parsing. | The root regression suite passed 771 tests. The affected DF tests passed 85 tests. A real Query → Timing ECO → EF → DF → Query handoff preserved the baseline checkpoint and returned equivalent reported timing. EF registered two ECO model receipts. |
| P3 | Qualify a public release. | Publish the intended source pins after approval, confirm SDK licensing, then run the documented example from a public clone. Complete clean-environment acceptance for Flow Agent, DPLEvolve, and GoalEvolve. |

GCD is a small workflow check. The smoke result had setup and hold worst slack of 39.032 ps and 110.505 ps respectively, with zero TNS in both checks. Its one-round ECO session kept the original routed checkpoint. Paper-scale search and statistical results have their own experimental protocols and records.

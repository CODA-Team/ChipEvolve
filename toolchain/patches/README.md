# Common-toolchain research patches

`restore-original-tns-policy.patch` restores the original GoalEvolve p0 TNS endpoint coverage, bounded paths per endpoint, and TNS/WNS collateral acceptance guards on the common OpenROAD source. It preserves the measured Student03 unaccepted-suffix journal rollback and its telemetry.

Apply to a private source copy before building. Keep running campaigns and released lineage snapshots immutable.

```bash
git apply --check /absolute/path/to/restore-original-tns-policy.patch
git apply /absolute/path/to/restore-original-tns-policy.patch
```

The patch base is the platform common-source `src/rsz/src/policy/SetupTnsPolicy.cc`, SHA256 `1607c819ca173a20cec626299569601725ba4eb07e1e6887e5295baa952448bc`. The original research file is `artifact_evaluation/lineage/openroad_power/p0/source/src/rsz/src/policy/SetupTnsPolicy.cc`, SHA256 `37a01a47379cd4481ef91654a172241ffd637a9fc37b0509bba97a9e7b715577`.

Regenerate the native repository graph for the resulting source, then build and evaluate through Execution Foundation. Record the new source and binary hashes. Current source/AST qualification and live build evidence are recorded in ChipEvolve's A30 report; final PPA acceptance remains pending actual measurement.

## Measured-policy path lifetime

`fix-measured-policy-path-lifetime.patch` repairs two lifetime errors in the existing experimental `MeasuredCriticalPathPolicy`: candidate apply/undo invalidates borrowed STA paths, and the winning candidate can outlive the local `Target` vector it references. Each generator now resolves live path handles for its original selected driver; the winning candidate keeps its target alive through commit. Failed shadow applications also refresh timing after rollback.

The patch preserves target ranking, generator selection, scoring, acceptance guards, the original move budget, and RC refresh policies. It does not enable this experimental policy by default or establish final PPA improvement. Apply only to a new private source copy, regenerate its repository graph, and build through EF as above.

Exact input files:

| File under `src/rsz/src/policy/` | Base SHA256 |
|---|---|
| `MeasuredCriticalPathPolicy.cc` | `29b9671fcc6afb6a4d37163861b10bb76ab61276f6087a915f8a2a0ba3c61b63` |
| `MeasuredCriticalPathPolicy.hh` | `9e09c5951175532ae307a969ae7934ee58dc3be9b40b3426f61a98d80e9ee477` |

The A38 EF regression replays both previously crashing recipes with their original inputs, SDC, seven-action sequence, and 40-move budget. Both exit successfully (40 and 35 committed moves); a non-measured TNS control retains all 25 checkpoint metrics and its output netlist exactly. The measured recipes still have negative final setup slack, so they are compatibility regressions, not accepted optimization results. Build identity and raw run receipts live in ChipEvolve's `var/business/a38-goal-path-lifetime-20261025/`; the root A38 report records their public EF handles.

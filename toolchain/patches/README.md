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

## RMP sequential-neighbor admission on connected supplies

`fix-rmp-supply-sequential-admission.patch` excludes POWER/GROUND nets from
`Restructure::touchesSequentialPin`. A shared supply is not a sequential signal
dependency: after platform handoff, connected VDD/VSS otherwise makes ordinary
combinational cells appear adjacent to every flip-flop and can eliminate all
path-cone candidates. Real signal and clock connections remain protected, as do
the other editable-cell, clock-network, STA, rollback and acceptance guards.

The verified base is `src/rmp/src/Restructure.cpp`, SHA256
`7b29e85e7f8f2597a2a54bcc2c9d9f0f610106aca01016c7ece9e2d3072852fe`.
Apply with `git apply --check` to a new private source copy, regenerate its native
repository graph, and build through EF. Never rewrite a measured source or a
released lineage snapshot. The native build donor must match the actual compile
database; a nested cached build can retain an older workspace in its Makefiles.

`tests/unit/test_rmp_supply_admission_patch.py` applies the real patch to the
original predicate and compiles it with topology test doubles. It reproduces the
two original VDD/VSS false positives and checks ten repaired boundaries,
including real flip-flop data/clock neighbors and mixed supply/signal cases.
Platform EF input diagnostics and native execution evidence are recorded under
ChipEvolve's `var/business/a68-rmp-candidate-admission-20261026/`. Candidate
admission alone does not establish an accepted PPA improvement.

## RMP placement across macro-cut row fragments

`fix-rmp-row-fragment-projection.patch` selects the nearest fitting row fragment
using both horizontal and vertical projection distance. Choosing a row only by
height can clamp a replacement cell to a distant fragment when macros split a
placement row. The patch retains floor-to-grid alignment, row orientation,
deterministic ties, and the original mapping, STA, acceptance and rollback rules.
Fragments narrower than the replacement master are excluded.

The base `src/cut/src/blif.cpp` SHA256 is
`7043b0df1f76a6011f2be373a3cdadf39b669895cf818e3d19c6ff2bd6d23e58`.
Apply only to a new private source copy with `git apply --check`, regenerate its
repository graph and build through EF; historical sources and binaries remain
immutable. `tests/unit/test_rmp_row_fragment_patch.py` compiles the exact original
and repaired functions against split, continuous, narrow, negative-coordinate
and orientation fixtures. Actual input diagnosis and subsequent native checks
are recorded in ChipEvolve's A71/A72 reports. Correct placement alone does not
establish accepted PPA improvement.

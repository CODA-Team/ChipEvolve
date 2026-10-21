# Common-toolchain research patches

`restore-original-tns-policy.patch` restores the original GoalEvolve p0 TNS endpoint coverage, bounded paths per endpoint, and TNS/WNS collateral acceptance guards on the common OpenROAD source. It preserves the measured Student03 unaccepted-suffix journal rollback and its telemetry.

Apply to a private source copy before building. Keep running campaigns and released lineage snapshots immutable.

```bash
git apply --check /absolute/path/to/restore-original-tns-policy.patch
git apply /absolute/path/to/restore-original-tns-policy.patch
```

The patch base is the platform common-source `src/rsz/src/policy/SetupTnsPolicy.cc`, SHA256 `1607c819ca173a20cec626299569601725ba4eb07e1e6887e5295baa952448bc`. The original research file is `artifact_evaluation/lineage/openroad_power/p0/source/src/rsz/src/policy/SetupTnsPolicy.cc`, SHA256 `37a01a47379cd4481ef91654a172241ffd637a9fc37b0509bba97a9e7b715577`.

Regenerate the native repository graph for the resulting source, then build and evaluate through Execution Foundation. Record the new source and binary hashes. Current source/AST qualification and live build evidence are recorded in ChipEvolve's A30 report; final PPA acceptance remains pending actual measurement.

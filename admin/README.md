# Installation, checks and experiment records

Start with the root [quickstart](../README.md) for a new installation. The
[file catalog](FILE_CATALOG.csv) classifies each current file under `admin/`
and records its consumers and proposed destination. `external_use` identifies
files used by the public installation and runtime preparation paths.

## Public installation and runtime tools

| Files | When they are used |
|---|---|
| `checkout_modules.sh` | Check out the module revisions fixed by the root repository. |
| `bootstrap.py`, `package_release.py`, `install_workspace.py`, `requirements-constraints.txt` | Build the pinned wheels and install separate project environments. Bootstrap invokes both helper scripts and the shared dependency constraints. |
| `release/stack.py`, `release/gcd_flow.py` | Prepare, start, inspect and stop a local EF/DF instance. Stack uses `gcd_flow.py` when preparing the native Flow binding. |
| `release/prepare_dpl.py`, `release/prepare_goal.py`, `release/native_toolchain.py` | Prepare specialist source and build bindings. DPL also uses the stack and GCD Flow helpers. |
| `release/build_arm_orfs.sh`, `release/package_arm_orfs.sh` | Build and package the pinned native ARM64 toolchain. |

After preparation, `chip-evolve.py` and `chip_evolve/` provide the business
commands. Execution and data services use the installed module wheels. Instance
configuration, logs and checkpoints live in `var/`. Source revisions and
upstream identities are recorded in [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json).

## Automated checks

Run `python3 dev.py root check` from the root repository. It checks installed
dependency consistency, root code lint and formatting, and every
`admin/test_*.py` test. The architecture tests inspect imports at every AST
depth, reject cyclic groups and check the declared layer of every root module.

The catalog marks scripts imported or invoked by the root tests as
`test_support`. These helpers include historical experiment operations that
the tests still exercise. The ARM64 workflow also uses
`release/capture_instance_receipts.py` to verify registered delivery artifacts.

## Archive mapping

The catalog records existing paths alongside proposed destinations. Runtime
tools use their current paths. Test relocation proposals point to
`admin/testing/`. Historical records point to `admin/archive/records/`, and
experiment and ablation scripts point to `admin/archive/experiments/`.
Consumer references identify the imports or file lookups to update during a
future move.

`release/build_code_delivery.py`, `release/build_final_code_delivery.py` and
`release/REPLAY.md` describe earlier bundle deliveries. The current public
installation uses the bootstrap and wheel path listed above. Files marked
`untracked` are local work whose release inclusion needs an explicit source
checkpoint.

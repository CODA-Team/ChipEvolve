# Install and operate the platform

Start with the [quickstart](../README.md). This directory owns installation and
service preparation; business commands start at `chip-evolve.py`.

| Files | Responsibility |
|---|---|
| `checkout_modules.sh` | Check the nine Git pins against the source manifest. |
| `bootstrap.py`, `package_release.py`, `install_workspace.py`, `requirements-constraints.txt` | Build pinned wheels and install ten independent environments. |
| `release/stack.py` | Prepare, start, inspect and safely stop a named EF/DF instance. |
| `release/gcd_flow.py` | Shared GCD recipe, with an optional native Flow binding. |
| `release/profile_bridge.py` | Fixed stdlib bridge to the root profile/resource owners through the installed client interpreter. |
| `release/prepare_dpl.py`, `release/prepare_goal.py`, `release/native_toolchain.py` | Prepare source/build bindings after checking real capacity. |
| `release/build_arm_orfs.sh`, `release/package_arm_orfs.sh` | Produce the pinned native ARM64 toolchain. |

The root integration layout and resource defaults have one source:
`chip_evolve/core/profiles/`. A prepared instance binds their identities,
the actual image and installed Toolkits files in `runtime-profile.json`.
`capacity-receipt.json` identifies an owned local service's startup capacity.
Stop/status retain access to the original owned processes even if a profile
has become invalid. Instances, environments, wheels and logs belong under
`var/` or the existing per-project `.venv` locations; they are not release source.

Run `python3 dev.py root check` for dependency, lint, formatting and all root
`tests/test_*.py` checks. Maintained experiment helpers used by tests live in
`tests/support/`; the ARM workflow also uses its capture-instance helper.

[FILE_CATALOG.csv](FILE_CATALOG.csv) records original and **current** paths,
consumers and local-only exceptions. The 377 historical files have moved to
[archive/](../archive/README.md), with SHA256 preserved. Seventeen original
unaccepted files remain protected in the owner's original workspace and are
excluded from the clean delivery; an absent local-only row is not a missing
runtime dependency. New runtime and test files are cataloged explicitly.

For a protected path already tracked in the public baseline, its earlier committed
version may remain in this clean checkout; the owner's unaccepted bytes or
modifications are excluded and stay untouched in the original workspace.

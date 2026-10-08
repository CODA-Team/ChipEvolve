# EDA Toolkits

OpenROAD/ORFS tool commands and native result normalization live here. Execution
Foundation manages their lifecycle through its existing plugin contract.
Data Foundation stores and relates the exported facts and source identities.

Install a wheel into a dedicated environment, then materialize plugin manifests
in a runtime directory using `eda-toolkit configure --output DIR`. The manifest
uses that environment's Python and the installed module. It contains no copied
adapter code or dependency on a sibling checkout. Point Execution Foundation's
`--plugins-root` at that directory; admission remains an EF-owned decision.

`eda-toolkit doctor --config CONFIG` checks explicit tool configuration. Running
an analysis requires an explicit submission; reading data never runs a tool.
Tool binaries, ORFS checkout and licensed technology libraries are deployment
inputs, and are not bundled in the wheel.

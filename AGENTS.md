# Toolkit boundaries

This independent project owns tool discovery, OpenROAD/ORFS commands, native
input loading, Tcl, tool-specific parsing and export. It consumes installed
Execution Foundation contracts/client wheels; it never imports the kernel or
Data Foundation business implementation. Runtime files belong in configured
state directories. Cross-project editable installs and source-path injection
are prohibited. Preserve native source evidence and original failure records.

The native adapter was moved with its tests from Execution Foundation. Protect
the existing protocol and calculation behavior before extending capabilities.

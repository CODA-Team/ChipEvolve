#!/usr/bin/env bash
# Source after activating the Python environment and your ORFS toolchain.
# Explicit overrides take precedence over PATH lookup.
export OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad || true)}"
export YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys || true)}"
export STA_EXE="${STA_EXE:-$(command -v sta || true)}"
if [[ -z "$OPENROAD_EXE" || ! -x "$OPENROAD_EXE" || -z "$YOSYS_EXE" || ! -x "$YOSYS_EXE" ]]; then
    echo 'Set OPENROAD_EXE and YOSYS_EXE to your executable ORFS tool binaries, or add them to PATH.' >&2
    return 1 2>/dev/null || exit 1
fi

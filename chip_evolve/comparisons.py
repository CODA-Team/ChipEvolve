"""Legacy module runner; use chip_evolve.workflow.comparisons for development."""

import sys
from .workflow import comparisons as implementation

if __name__ == "__main__":
    raise SystemExit(implementation.main())
else:
    sys.modules[__name__] = implementation

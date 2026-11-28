"""Legacy module runner; use chip_evolve.workflow.continuation for development."""

import sys
from .workflow import continuation as implementation

if __name__ == "__main__":
    raise SystemExit(implementation.main())
else:
    sys.modules[__name__] = implementation

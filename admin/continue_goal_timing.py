"""Compatibility entry for the original A7 driver; use chip-evolve continue-goal."""

from chip_evolve.continuation import (  # noqa: F401
    checkpoint_method,
    checkpoint_producer,
    continuation_contract,
    main,
    run,
)

if __name__ == "__main__":
    main()

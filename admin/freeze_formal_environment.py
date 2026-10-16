"""Freeze an existing source control and real EF tool probe, without a search."""

import argparse
from pathlib import Path

from chip_evolve.config import Deployment, read
from chip_evolve.environment import freeze_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    deployment = Deployment(args.config)
    experiment = deployment.experiment(read(args.source)["design_id"], args.key)
    print(
        freeze_environment(
            deployment, args.source.resolve(), args.qualification.resolve(), experiment
        )
    )


if __name__ == "__main__":
    main()

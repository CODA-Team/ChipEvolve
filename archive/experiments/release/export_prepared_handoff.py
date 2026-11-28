"""Export the existing typed task package without creating another identity."""

import argparse
import hashlib
import json
from pathlib import Path

from query_agent.domain.investigation import InvestigationState
from query_agent.domain.handoff import HandoffPackage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    states = list((args.state_root / "investigations").glob("*/state.json"))
    if len(states) != 1:
        raise ValueError("Replay needs exactly one saved investigation")
    path = states[0]
    state = InvestigationState.model_validate_json(path.read_bytes())
    if len(state.handoff_packages) != 1:
        raise ValueError("Exactly one real prepared package is required")
    package = HandoffPackage.model_validate(state.handoff_packages[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(package.model_dump_json(indent=2) + "\n")
    receipt = {
        "state_path": str(path.resolve()),
        "state_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "package_path": str(args.output.resolve()),
        "package_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "handoff_id": package.handoff_id,
        "new_handoff_created": False,
        "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with args.output.with_suffix(".export-receipt.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

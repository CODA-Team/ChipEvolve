"""Explicit configuration and tool operations."""
import argparse
import json
from pathlib import Path
from .configuration import configure_plugins
from .environment import doctor


def main() -> int:
    parser = argparse.ArgumentParser(prog='eda-toolkit')
    commands = parser.add_subparsers(dest='command', required=True)
    configure = commands.add_parser('configure')
    configure.add_argument('--output', type=Path, required=True)
    configure.add_argument('--image')
    configure.add_argument('--activity-lock')
    inspect = commands.add_parser('doctor')
    inspect.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'configure':
        print(json.dumps(configure_plugins(args.output, image=args.image, activity_lock=args.activity_lock), indent=2))
    elif args.command == 'doctor':
        result = doctor(json.loads(args.config.read_text()))
        print(json.dumps(result, indent=2))
        return 0 if result['passed'] else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

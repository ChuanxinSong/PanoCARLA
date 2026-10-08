"""Replay one or more CSV trajectories, sequentially, on one CARLA server."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys

from record_options import add_recording_arguments, validate_recording_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv_paths', nargs='+', required=True,
                        help='CSV paths from the same town (shell globs are accepted)')
    parser.add_argument('--dry_run', action='store_true', help='Print commands without connecting')
    add_recording_arguments(parser)
    args = parser.parse_args()
    validate_recording_arguments(parser, args)
    csv_paths = list(dict.fromkeys(Path(p).expanduser().resolve() for p in args.csv_paths))
    for path in csv_paths:
        if not path.is_file():
            parser.error(f'CSV does not exist: {path}')

    script = Path(__file__).with_name('record_2stage.py')
    for path in csv_paths:
        command = [sys.executable, str(script), '--csv_path', str(path)]
        for key, value in vars(args).items():
            if key in ('csv_paths', 'dry_run'):
                continue
            if isinstance(value, bool):
                if value:
                    command.append(f'--{key}')
            else:
                command.extend([f'--{key}', str(value)])
        print(shlex.join(command), flush=True)
        if not args.dry_run:
            subprocess.run(command, check=True)


if __name__ == '__main__':
    main()

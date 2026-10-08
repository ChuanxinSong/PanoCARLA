"""Stitch recordings and create collision-annotated RGB-D preview videos."""
import argparse
from pathlib import Path
import shlex
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base_dirs', nargs='+', required=True,
                        help='Recording directories, each containing six camera views')
    parser.add_argument('--original_fov', type=float, required=True)
    parser.add_argument('--num_process', type=int, default=4)
    parser.add_argument('--fps', type=int, default=20)
    parser.add_argument('--equi_height', type=int, default=1200)
    parser.add_argument('--equi_width', type=int, default=2400)
    parser.add_argument('--re_stitch', action='store_true')
    parser.add_argument('--dry_run', action='store_true')
    args = parser.parse_args()
    if min(args.num_process, args.fps, args.equi_height, args.equi_width) <= 0:
        parser.error('Process count, FPS and image dimensions must be positive')
    if not 90 <= args.original_fov < 180 or not args.original_fov.is_integer():
        parser.error('--original_fov must be an integer in [90, 180)')
    if args.equi_width != 2 * args.equi_height or args.equi_height % 2:
        parser.error('Panoramas must have even height and width = 2 * height')
    base_dirs = list(dict.fromkeys(Path(p).expanduser().resolve() for p in args.base_dirs))
    for path in base_dirs:
        if not path.is_dir():
            parser.error(f'Recording directory does not exist: {path}')

    scripts = Path(__file__).resolve().parent
    for path in base_dirs:
        stitch = [sys.executable, str(scripts / 'equi_extract_for_fov100_multiprocess.py'),
                  '--base_dir', str(path)]
        for key in ('original_fov', 'num_process', 'equi_height', 'equi_width'):
            stitch.extend([f'--{key}', str(getattr(args, key))])
        if args.re_stitch:
            stitch.append('--re_stitch')
        video = [sys.executable, str(scripts / 'stage2vis_rgbd2video.py'),
                 '--base_dir', str(path), '--fps', str(args.fps)]
        for command in (stitch, video):
            print(shlex.join(command), flush=True)
            if not args.dry_run:
                subprocess.run(command, check=True)


if __name__ == '__main__':
    main()

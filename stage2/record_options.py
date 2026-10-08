"""Shared CLI for single-route and batch CSV replay."""


def add_recording_arguments(parser):
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=11536)
    parser.add_argument('--map', required=True, choices=[
        'Town01', 'Town02', 'Town03', 'Town04', 'Town05', 'Town06',
        'Town07', 'Town10HD', 'Town11', 'Town12', 'Town13', 'Town15'])
    parser.add_argument('--output_root', default='recordings')
    parser.add_argument('--height_mode', choices=['relative', 'absolute'], default='relative',
                        help='relative: CSV z + offset; absolute: fixed world Z')
    parser.add_argument('--camera_height', type=float, default=4.0,
                        help='Height/offset in metres; initial offset in dynamic mode')
    parser.add_argument('--dynamic_height', action='store_true')
    parser.add_argument('--min_height', type=float, default=2.0)
    parser.add_argument('--max_height', type=float, default=20.0)
    parser.add_argument('--vehicle_density', type=float, default=60.0,
                        help='Percentage of spawn points used in dynamic mode')
    parser.add_argument('--no_other_cars', action='store_true',
                        help='Clear existing vehicles/walkers and do not spawn traffic')
    parser.add_argument('--width', type=int, default=800)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--fov', type=int, default=120)
    parser.add_argument('--fps', type=int, default=20)
    parser.add_argument('--re_record', action='store_true',
                        help='Clear this route’s raw sensor files/logs and record from scratch')


def validate_recording_arguments(parser, args):
    import math
    for name in ('camera_height', 'min_height', 'max_height', 'vehicle_density'):
        if not math.isfinite(getattr(args, name)):
            parser.error(f'--{name} must be finite')
    if args.fps <= 0 or args.width <= 0 or args.height <= 0:
        parser.error('FPS and image dimensions must be positive')
    if args.width != args.height:
        parser.error('The panorama pipeline currently requires square source images')
    if not 90 <= args.fov < 180:
        parser.error('--fov must be in [90, 180) for six-view coverage')
    if not 0 <= args.vehicle_density <= 100:
        parser.error('--vehicle_density must be in [0, 100]')
    if args.dynamic_height:
        if args.height_mode != 'relative':
            parser.error('--dynamic_height requires --height_mode relative')
        if not 0 <= args.min_height < args.max_height:
            parser.error('Dynamic heights must satisfy 0 <= min_height < max_height')
        if not args.min_height <= args.camera_height <= args.max_height:
            parser.error('--camera_height must lie within the dynamic height range')

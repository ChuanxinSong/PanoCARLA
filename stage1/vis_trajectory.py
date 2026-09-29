#!/usr/bin/env python

import carla
import argparse
import csv
import time
import re


def read_trajectory_from_csv(filepath):
    """Read x, y, z coordinates from a trajectory CSV."""
    trajectory_points = []
    try:
        with open(filepath, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"Reading trajectory from {filepath}...")
            for row in reader:
                try:
                    x = float(row['x'])
                    y = float(row['y'])
                    z = float(row['z'])

                    # Raise the line above the road surface.
                    location = carla.Location(x, y, z + 0.2)
                    trajectory_points.append(location)
                except (ValueError, KeyError) as e:
                    print(f"Skipping row due to error: {e}. Row: {row}")
                    continue
            print(f"Successfully read {len(trajectory_points)} points.")
    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

    return trajectory_points


def main():
    """Draw the recorded trajectory in CARLA."""
    argparser = argparse.ArgumentParser(
        description='Visualize a recorded CARLA trajectory from a CSV file.')
    argparser.add_argument(
        'csv_file',
        help='Path to the CSV file containing the trajectory data.')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='localhost',
        help='IP of the host server (default: localhost)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=3346,
        type=int,
        help='TCP port to listen to (default: 3246)')
    argparser.add_argument(
        '--map',
        metavar='MAP',
        default='Town04',
        help='Name of the map to load, should be the same map where the data was recorded (e.g., Town04)')
    argparser.add_argument(
        '--life_time',
        default=6000.0,
        type=float,
        help='How long the trajectory lines should remain visible in seconds (default: 60.0)')
    argparser.add_argument(
        '--thickness',
        default=1.0,
        type=float,
        help='Thickness of the trajectory lines (default: 0.1)')
    argparser.add_argument(
        '--arrow_size',
        default=2,
        type=float,
        help='Size of the arrow head (default: 1.5)')

    argparser.add_argument(
        '--brightness',
        default=1.0,
        type=float,
        help='Brightness factor for the color (0.0=black, 1.0=original). E.g., 0.7 for 70%% brightness.')
    argparser.add_argument(
        '--color',
        default=None,
        help='Color of the trajectory line in R,G,B format (e.g., "255,0,0"). If not provided, color is assigned automatically based on filename.')

    argparser.add_argument(
        '--no_other',
        action='store_true',
        help='Clear all previously drawn trajectories before drawing the new one.')

    args = argparser.parse_args()

    path_label = None

    preset_colors = [
        carla.Color(0, 0, 0),
        carla.Color(0, 0, 255),
        carla.Color(255, 0, 0),
        carla.Color(255, 255, 255),
        carla.Color(255, 255, 0),
        carla.Color(255, 165, 0),
        carla.Color(0, 100, 0),
        carla.Color(128, 128, 128),
        carla.Color(128, 0, 128),
        carla.Color(255, 192, 203),
        carla.Color(165, 42, 42)
    ]

    path_color = None

    if args.color:
        print(f"User specified color '{args.color}'. Using it.")
        try:
            r, g, b = [int(x) for x in args.color.split(',')]
            path_color = carla.Color(r, g, b)
        except ValueError:
            print("Error: Invalid color format. Please use R,G,B (e.g., '255,0,0').")
            return
    else:
        print("No color specified. Attempting to determine color from filename...")

        # Select a preset color from a clip number in the filename.
        match = re.search(r'clip(\d+)', args.csv_file)

        if match:
            path_label = match.group(0)
            path_number = int(match.group(1))
            print(f"Detected path number: {path_number}")

            if 1 <= path_number <= len(preset_colors):
                path_color = preset_colors[path_number - 1]
                print(f"Automatically assigned color for path {path_number}.")
            else:
                print(f"Warning: Path number {path_number} is out of the preset color range (1-{len(preset_colors)}).")
        else:
            print("Warning: Could not detect path number from filename.")

    if path_color is None:
        path_color = carla.Color(255, 0, 0)
        print("Using default fallback color (Red).")

    brightness_factor = max(0.0, min(1.0, args.brightness))
    if brightness_factor != 1.0:
        print(f"Adjusting color brightness by a factor of {brightness_factor}...")
        new_r = int(path_color.r * brightness_factor)
        new_g = int(path_color.g * brightness_factor)
        new_b = int(path_color.b * brightness_factor)
        path_color = carla.Color(new_r, new_g, new_b)

    client = None
    try:
        print(f"Connecting to CARLA server at {args.host}:{args.port}...")
        client = carla.Client(args.host, args.port)
        client.set_timeout(10.0)

        world = client.get_world()
        current_map_name = world.get_map().name.split('/')[-1]

        if current_map_name == args.map:
            print(f"Correct map '{args.map}' is already loaded. Skipping map load.")
        else:
            print(f"Current map is '{current_map_name}', loading desired map '{args.map}'...")
            world = client.load_world(args.map)

            world.wait_for_tick()

        debug = world.debug
        print("Connection and map setup successful.")

        if args.no_other:
            print("The --no_other flag is set. Clearing all previous debug drawings...")
            client.reload_world()
            world.wait_for_tick()

            world = client.get_world()
            debug = world.debug
            print("Previous drawings cleared.")

        trajectory = read_trajectory_from_csv(args.csv_file)

        if not trajectory or len(trajectory) < 2:
            print("Not enough points to draw a trajectory. Exiting.")
            return

        if path_label:
            start_label_text = f"{path_label}_0"
            start_location = trajectory[0]

            start_location.z += 1.5

            world.debug.draw_string(
                start_location,
                start_label_text,
                draw_shadow=False,
                color=path_color,
                life_time=args.life_time,
                persistent_lines=True
            )
            print(f"Drawing start label '{start_label_text}' at the start of the trajectory.")

            end_label_text = f"{path_label}_1"
            end_location = trajectory[-1]

            end_location.z += 1.5

            world.debug.draw_string(
                end_location,
                end_label_text,
                draw_shadow=False,
                color=path_color,
                life_time=args.life_time,
                persistent_lines=True
            )
            print(f"Drawing end label '{end_label_text}' at the end of the trajectory.")

        print("Drawing trajectory... The lines will be visible in the simulator.")

        for i in range(len(trajectory) - 1):
            p1 = trajectory[i]
            p2 = trajectory[i + 1]
            debug.draw_line(
                p1,
                p2,
                thickness=args.thickness * 0.5,
                color=path_color,
                life_time=args.life_time
            )

        # Draw a direction arrow every 200 trajectory samples.
        arrow_interval = 200
        print(f"Overlaying direction arrows at intervals of {arrow_interval} points.")
        for i in range(0, len(trajectory) - 1, arrow_interval):
            p1 = trajectory[i]
            p2 = trajectory[i + 1]

            if p1.distance(p2) > 0.1:
                debug.draw_arrow(
                    p1,
                    p2,
                    thickness=args.thickness,
                    arrow_size=args.arrow_size,
                    color=path_color,
                    life_time=args.life_time
                )

        print("\nTrajectory visualization complete.")
        print(f"The path will remain visible for {args.life_time} seconds.")
        print("You can now navigate in the CARLA spectator view to inspect the path.")
        print("Press Ctrl+C in this terminal to exit.")

        while True:
            world.wait_for_tick()
            time.sleep(1)

    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        print("Script finished.")


if __name__ == '__main__':
    main()

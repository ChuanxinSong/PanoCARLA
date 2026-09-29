import carla
import time
import sys


# Distance in meters for displaying nearby spawn poses.
PROXIMITY_THRESHOLD = 10.0


def print_city_info(client):
    """List the current map and available maps."""
    world = client.get_world()
    current_map = world.get_map().name
    available_maps = client.get_available_maps()

    print("\n" + "=" * 60)
    print("Maps:")
    print(f"   Current map: {current_map}")
    print("   Available maps:")
    for i, map_name in enumerate(available_maps):
        marker = "->" if map_name == current_map else "  "
        print(f"   {marker} [{i}] {map_name}")
    print("=" * 60)
    return available_maps


def change_city(client, available_maps):
    """Load the selected map."""
    try:
        print("\nEnter a map index, or press Enter to keep the current map:")
        user_input = input().strip()

        if not user_input:
            return False

        city_index = int(user_input)
        if 0 <= city_index < len(available_maps):
            selected_map = available_maps[city_index]
            current_map = client.get_world().get_map().name

            if selected_map in current_map:
                print(f"Map '{selected_map.split('/')[-1]}' is already loaded.")
                return False
            else:
                print(f"Loading map: {selected_map.split('/')[-1]}")
                client.load_world(selected_map)
                print("Map loaded.")
                return True
        else:
            print("Invalid map index.")
            return False
    except ValueError:
        print("Enter a valid number.")
        return False
    except Exception as e:
        print(f"Could not load map: {e}")
        return False


def main():
    """Display spawn poses and track the spectator position."""
    client = None
    try:
        client = carla.Client('localhost', 3346)
        client.set_timeout(100.0)
        print("Connected to CARLA.")

        available_maps = print_city_info(client)
        if change_city(client, available_maps):
            time.sleep(2)

        world = client.get_world()
        carla_map = world.get_map()
        debug_helper = world.debug

        spawn_points = carla_map.get_spawn_points()
        print(f"Drawing {len(spawn_points)} spawn points...")

        for i, spawn_point in enumerate(spawn_points):
            debug_helper.draw_string(
                spawn_point.location + carla.Location(z=2.0),
                str(i),
                draw_shadow=False,
                color=carla.Color(r=255, g=255, b=0),
                life_time=0,
                persistent_lines=True
            )

            debug_helper.draw_arrow(
                spawn_point.location,
                spawn_point.location + spawn_point.get_forward_vector() * 2,
                thickness=0.1,
                arrow_size=0.2,
                color=carla.Color(r=0, g=255, b=0),
                life_time=0,
                persistent_lines=True
            )

        print("Yellow labels show spawn indices; green arrows show headings.")
        print("\n" + "=" * 80)
        print("Pose tracking started.")
        print(f"   Move within {PROXIMITY_THRESHOLD} m of a spawn point to inspect its pose.")
        print("   The terminal shows the nearest spawn pose or the spectator pose. Press Ctrl+C to exit.")
        print("=" * 80 + "\n")

        spectator = world.get_spectator()
        while True:
            spectator_transform = spectator.get_transform()
            spectator_location = spectator_transform.location

            nearby_spawn_points = []
            for i, spawn_point in enumerate(spawn_points):
                dist = spectator_location.distance(spawn_point.location)
                if dist < PROXIMITY_THRESHOLD:
                    nearby_spawn_points.append((i, spawn_point, dist))

            if nearby_spawn_points:
                nearby_spawn_points.sort(key=lambda x: x[2])
                closest_index, closest_spawn_point, closest_dist = nearby_spawn_points[0]

                loc = closest_spawn_point.location
                rot = closest_spawn_point.rotation
                location_str = f"carla.Location(x={loc.x:.2f}, y={loc.y:.2f}, z={loc.z:.2f})"
                rotation_str = f"carla.Rotation(pitch={rot.pitch:.2f}, yaw={rot.yaw:.2f}, roll={rot.roll:.2f})"
                sys.stdout.write(f"\rSpawn point [{closest_index}] {location_str}  |  {rotation_str}      ")
                sys.stdout.flush()

                for spawn_index, spawn_point, _ in nearby_spawn_points:
                    sp_loc = spawn_point.location
                    sp_rot = spawn_point.rotation

                    loc_text = f"X:{sp_loc.x:.1f} Y:{sp_loc.y:.1f} Z:{sp_loc.z:.1f}"
                    rot_text = f"P:{sp_rot.pitch:.1f} Y:{sp_rot.yaw:.1f} R:{sp_rot.roll:.1f}"

                    # Refresh nearby labels so they disappear when the spectator moves away.
                    draw_lifetime = 0.2

                    debug_helper.draw_string(spawn_point.location + carla.Location(z=1.2), loc_text, False,
                                             carla.Color(255, 255, 255), draw_lifetime)
                    debug_helper.draw_string(spawn_point.location + carla.Location(z=0.7), rot_text, False,
                                             carla.Color(255, 255, 255), draw_lifetime)
            else:
                loc = spectator_location
                rot = spectator_transform.rotation
                location_str = f"carla.Location(x={loc.x:.2f}, y={loc.y:.2f}, z={loc.z:.2f})"
                rotation_str = f"carla.Rotation(pitch={rot.pitch:.2f}, yaw={rot.yaw:.2f}, roll={rot.roll:.2f})"
                sys.stdout.write(f"\rSpectator pose: {location_str}  |  {rotation_str}      ")
                sys.stdout.flush()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Finished.")


if __name__ == '__main__':
    main()

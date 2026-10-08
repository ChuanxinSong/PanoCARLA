"""Replay a Stage 1 CSV into six-view RGB, metric depth and semantic labels."""
import json
import hashlib
from pathlib import Path
import carla
import numpy as np
from PIL import Image
import os
import queue
from tqdm import tqdm
import pandas as pd
import argparse
import random
import sys
from record_options import add_recording_arguments, validate_recording_arguments


def process_and_save_data(frame_id, rgb_data, depth_data, segmentation_tags, output_base_dir, fov):
    """Save six-view RGB images, metric depth arrays and semantic labels."""
    for name, image_data in rgb_data.items():
        img = Image.fromarray(image_data)
        output_dir = os.path.join(output_base_dir, f'rgb_{name}_fov{fov}')
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f'{frame_id:06d}.png')
        img.save(path)

    for name, image_data in depth_data.items():
        # Store metric depth as floating-point NPY arrays.
        output_dir_raw = os.path.join(output_base_dir, f'depth_npy_{name}_fov_{fov}')
        os.makedirs(output_dir_raw, exist_ok=True)
        path_raw = os.path.join(output_dir_raw, f'{frame_id:06d}.npy')
        np.save(path_raw, image_data)

    for name, tag_array in segmentation_tags.items():
        # Store class IDs as single-channel PNGs.
        img = Image.fromarray(tag_array, mode='L')
        output_dir = os.path.join(output_base_dir, f'segmentation_{name}_fov{fov}')
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f'{frame_id:06d}.png')
        img.save(path)


def validate_map_and_csv_consistency(args):
    """Check the map against the CSV filename; warn if no map can be extracted."""
    try:
        csv_filename = os.path.basename(args.csv_path)
        parts = csv_filename.split('_')
        extracted_map_name = None
        for part in parts:
            if part.lower().startswith('town'):
                extracted_map_name = part
                break

        if extracted_map_name is None:
            raise ValueError("在CSV文件名中没有找到'town'关键字。")

        if extracted_map_name.lower() not in args.map.lower():
            print("\n❌ 错误：地图参数与轨迹文件名不匹配！")
            print(f"  > 命令行 --map 参数为: '{args.map}'")
            print(f"  > 从CSV文件名中提取的地图为: '{extracted_map_name}'")
            print("\n  请检查你的 --map 或 --csv_path 参数是否正确。")
            sys.exit(1)

        print(f"✅ 地图匹配验证通过: --map '{args.map}' 与 CSV文件名中的 '{extracted_map_name}' 一致。")

    except Exception as e:
        print(f"⚠️ 警告：无法从CSV文件名 '{args.csv_path}' 中自动提取地图名称。错误: {e}")
        print("   将跳过地图匹配检查。请手动确保您为该轨迹选择了正确的地图。")

def check_collision_with_ray(world, location, max_distance=1.0):
    """Check for ray hits within max_distance metres along the six world axes."""
    # Cast rays along the six world-axis directions.
    directions = [
        carla.Vector3D(1, 0, 0), carla.Vector3D(-1, 0, 0),
        carla.Vector3D(0, 1, 0), carla.Vector3D(0, -1, 0),
        carla.Vector3D(0, 0, 1), carla.Vector3D(0, 0, -1)
    ]

    for direction in directions:
        ray_end = location + direction * max_distance
        hit_results = world.cast_ray(location, ray_end)

        if hit_results:
            return True

    return False


def saved_prefix(output_dir, frames, fov):
    """Only resume a contiguous prefix with every enabled camera file present."""
    for index, frame in enumerate(frames):
        for view in ('front', 'back', 'left', 'right', 'up', 'down'):
            for folder, suffix in ((f'rgb_{view}_fov{fov}', '.png'),
                                   (f'depth_npy_{view}_fov_{fov}', '.npy'),
                                   (f'segmentation_{view}_fov{fov}', '.png')):
                if not (Path(output_dir) / folder / f'{frame:06d}{suffix}').is_file():
                    return index
    return len(frames)


def receive_frame(sensor_queue, expected_frame):
    """Discard stale callbacks; never label an image with another simulation frame."""
    import time
    deadline = time.monotonic() + 10.0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f'Sensor timed out at CARLA frame {expected_frame}')
        try:
            image = sensor_queue.get(timeout=remaining)
        except queue.Empty as error:
            raise TimeoutError(f'Sensor timed out at CARLA frame {expected_frame}') from error
        if image.frame == expected_frame:
            return image
        if image.frame > expected_frame:
            raise RuntimeError(f'Sensor skipped CARLA frame {expected_frame}: got {image.frame}')


class DynamicHeightManager:
    """Generate bounded height offsets using transitions, hovering and sinusoidal motion."""
    def __init__(self, initial_height=15.0, min_height=3.0, max_height=20.0):
        self.min_height = min_height
        self.max_height = max_height
        self.current_height = initial_height

        self.frames_in_pattern = 0
        self.pattern_duration = 0
        self.current_pattern = 'stable_hover'

        self.pattern_base_height = initial_height
        self.start_height = 0
        self.target_height = 0
        self.sin_amplitude = 0
        self.sin_frequency = 0

        self._initialize_new_pattern()

    def _initialize_new_pattern(self):
        """Alternate height transitions with hovering or sinusoidal motion."""
        self.frames_in_pattern = 0

        if self.current_pattern == 'smooth_transition':
            self.pattern_base_height = self.current_height
            new_maneuver = random.choice(['stable_hover', 'sinusoidal_wave'])
            self.current_pattern = new_maneuver
            self.pattern_duration = random.randint(20, 50)

            if new_maneuver == 'sinusoidal_wave':
                self.sin_amplitude = np.clip(random.uniform(0.5, 2.0), 0,
                    min(self.pattern_base_height - self.min_height, self.max_height - self.pattern_base_height))
                self.sin_frequency = random.uniform(0.05, 0.2)
        else:
            self.current_pattern = 'smooth_transition'
            self.start_height = self.current_height

            # Bound rejection sampling for narrow user-specified height ranges.
            for _ in range(100):
                self.target_height = random.uniform(self.min_height, self.max_height)
                if abs(self.target_height - self.start_height) > 2.0:
                    break
            self.pattern_duration = random.randint(30, 70)

    def get_current_height(self):
        """Return the height offset for the next frame, clipped to the configured bounds."""
        if self.frames_in_pattern >= self.pattern_duration:
            self._initialize_new_pattern()

        if self.current_pattern == 'stable_hover':
            self.current_height = self.pattern_base_height

        elif self.current_pattern == 'sinusoidal_wave':
            progress = self.sin_frequency * self.frames_in_pattern
            self.current_height = self.pattern_base_height + self.sin_amplitude * np.sin(progress)

        elif self.current_pattern == 'smooth_transition':
            progress = self.frames_in_pattern / self.pattern_duration
            self.current_height = self.start_height + (self.target_height - self.start_height) * progress

        self.frames_in_pattern += 1
        return np.clip(self.current_height, self.min_height, self.max_height)


def main():

    # All three modalities are part of this recording pipeline.
    RECORD_RGB = True
    RECORD_DEPTH = True
    RECORD_SEGMENTATION = True

    print("\n" + "="*40)
    print(" " * 12 + "数据录制配置")
    print("="*40)
    print(f" {'✅' if RECORD_RGB else '❌'}  RGB 图像:  [{'启用' if RECORD_RGB else '禁用'}]")
    print(f" {'✅' if RECORD_DEPTH else '❌'}  深度数据:  [{'启用' if RECORD_DEPTH else '禁用'}]")
    print(f" {'✅' if RECORD_SEGMENTATION else '❌'}  语义分割:  [{'启用' if RECORD_SEGMENTATION else '禁用'}]")
    print("="*40 + "\n")

    parser = argparse.ArgumentParser(description=__doc__)
    add_recording_arguments(parser)
    parser.add_argument('--csv_path', required=True)
    args = parser.parse_args()
    validate_recording_arguments(parser, args)

    validate_map_and_csv_consistency(args)

    TRAJECTORY_CSV_PATH = args.csv_path
    trajectory_df = pd.read_csv(TRAJECTORY_CSV_PATH)
    required = ['frame', 'timestamp', 'x', 'y', 'z', 'pitch', 'yaw', 'roll']
    if trajectory_df.empty or any(name not in trajectory_df for name in required):
        parser.error(f'CSV must contain nonempty columns: {required}')
    values = trajectory_df[required].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        parser.error('CSV values must be finite numbers')
    frames = trajectory_df['frame'].to_numpy(dtype=float)
    if (frames < 0).any() or (frames != np.floor(frames)).any() or (np.diff(frames) <= 0).any():
        parser.error('CSV frame IDs must be nonnegative, integral and strictly increasing')
    frame_ids = frames.astype(np.int64).tolist()
    CHOOSED_MAP = args.map

    filename = os.path.splitext(os.path.basename(args.csv_path))[0].replace("first_stage_", "")

    if args.dynamic_height:
        folder_suffix = f"rz_dynamic_{args.min_height}_{args.max_height}_fov{args.fov}"
        if args.no_other_cars:
            folder_suffix += "_no_car"
    else:
        height_prefix = 'rz' if args.height_mode == 'relative' else 'z'
        folder_suffix = f"{height_prefix}_{args.camera_height}_fov{args.fov}"

    folder_name = f"{filename}_{folder_suffix}"
    log_filename = f"{folder_name}_collision_log.csv"
    pose_log_filename = f"{folder_name}_pose_log.csv"

    OUTPUT_BASE_DIR = os.path.join(args.output_root, folder_name)
    log_file_path = os.path.join(OUTPUT_BASE_DIR, log_filename)
    pose_log_path = os.path.join(OUTPUT_BASE_DIR, pose_log_filename)
    print(f"📝 碰撞日志将保存在: {log_file_path}")

    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

    # Reject accidental reuse of a route directory with different capture settings.
    config_path = Path(OUTPUT_BASE_DIR) / 'recording_config.json'
    config = {key: value for key, value in vars(args).items()
              if key not in ('host', 'port', 'output_root', 'csv_path', 're_record')}
    config['csv_sha256'] = hashlib.sha256(Path(args.csv_path).read_bytes()).hexdigest()
    if config_path.exists() and not args.re_record:
        if json.loads(config_path.read_text()) != config:
            parser.error('Recording settings changed; use a new output root or --re_record')

    start_frame_index = 0 if args.re_record else saved_prefix(OUTPUT_BASE_DIR, frame_ids, args.fov)
    if start_frame_index == len(frame_ids):
        print('All frames are already recorded.')
        return
    if args.dynamic_height:
        # A new CARLA session cannot restore traffic or the random height state.
        start_frame_index = 0
    if start_frame_index == 0:
        for view in ('front', 'back', 'left', 'right', 'up', 'down'):
            for folder, suffix in ((f'rgb_{view}_fov{args.fov}', '.png'),
                                   (f'depth_npy_{view}_fov_{args.fov}', '.npy'),
                                   (f'segmentation_{view}_fov{args.fov}', '.png')):
                for old_file in (Path(OUTPUT_BASE_DIR) / folder).glob(f'*{suffix}'):
                    old_file.unlink()
    # Drop log rows at or after the first frame to be re-recorded.
    for log_path in (log_file_path, pose_log_path):
        if log_path == pose_log_path and not args.dynamic_height:
            continue
        if start_frame_index and Path(log_path).exists():
            log = pd.read_csv(log_path)
            log = log[log['frame_id'] < frame_ids[start_frame_index]]
            log.to_csv(log_path, index=False)
        else:
            Path(log_path).write_text('frame_id,x,y,z,yaw\n')
    config_path.write_text(json.dumps(config, indent=2) + '\n')

    HOST = args.host
    PORT = args.port


    height_manager = None
    if args.dynamic_height:
        print("✅ 已启用【动态高度模式】。")
        height_manager = DynamicHeightManager(
            initial_height=args.camera_height,
            min_height=args.min_height,
            max_height=args.max_height
        )
    else:
        print("ℹ️  当前为【固定高度模式】。")
        CAMERA_HEIGHT_Z = args.camera_height

    IMAGE_WIDTH = args.width
    IMAGE_HEIGHT = args.height
    FOV = args.fov
    FPS = args.fps


    actor_list = []
    client = None
    world = None
    original_settings = None
    traffic_manager = None

    try:
        client = carla.Client(HOST, PORT)
        client.set_timeout(200.0)
        print(f"\n✅ 成功连接！")

        world = client.get_world()
        if CHOOSED_MAP not in world.get_map().name:
            print(f"⏳ 当前地图为 '{world.get_map().name}'，与目标不符。正在加载新地图 '{CHOOSED_MAP}'...")
            world = client.load_world(CHOOSED_MAP)
            world.wait_for_tick()
            print(f"✅ 地图加载成功！当前地图: '{world.get_map().name.split('/')[-1]}'")
        else:
            print(f"✅ 无需切换，当前地图已是 '{CHOOSED_MAP}'。")

        original_settings = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1.0 / FPS
        world.apply_settings(settings)
        print(f"已切换到同步模式，帧率固定为 {FPS} FPS")


        if args.dynamic_height and not args.no_other_cars:
            print("ℹ️  动态高度模式已启用，正在尝试向世界中添加车辆...")

            spawn_points = world.get_map().get_spawn_points()
            total_spawn_points = len(spawn_points)

            density = max(0, min(100, args.vehicle_density)) / 100.0

            NUM_VEHICLES = int(total_spawn_points * density)

            print(f"当前地图 '{args.map}' 共有 {total_spawn_points} 个车辆生成点。")
            print(f"根据 {args.vehicle_density}% 的交通密度，将尝试生成 {NUM_VEHICLES} 辆车。")

            traffic_manager = client.get_trafficmanager(args.port + 3)
            traffic_manager.set_synchronous_mode(True)
            traffic_manager.set_global_distance_to_leading_vehicle(2.5)
            traffic_manager.set_hybrid_physics_mode(True)
            traffic_manager.set_respawn_dormant_vehicles(True)

            blueprints_vehicles = world.get_blueprint_library().filter('vehicle.*')
            spawn_points = world.get_map().get_spawn_points()

            print(f"正在生成 {NUM_VEHICLES} 辆自动驾驶汽车...")
            spawn_points = world.get_map().get_spawn_points()
            random.shuffle(spawn_points)

            spawn_commands = []
            for i in range(min(NUM_VEHICLES, len(spawn_points))):
                try:
                    blueprint = random.choice(blueprints_vehicles)
                    transform = spawn_points.pop()
                    spawn_commands.append(carla.command.SpawnActor(blueprint, transform))
                except:
                    continue

            responses = client.apply_batch_sync(spawn_commands, True)
            spawned_vehicles = []
            for response in responses:
                if not response.error:
                    spawned_vehicles.append(response.actor_id)

            for vehicle_id in spawned_vehicles:
                vehicle = world.get_actor(vehicle_id)
                actor_list.append(vehicle)
                vehicle.set_autopilot(True, traffic_manager.get_port())

            print(f"尝试生成 {len(spawn_commands)} 辆车，成功 {len(spawned_vehicles)} 辆。")

        else:
            print("ℹ️  固定高度/no_car模式已启用，正在清理世界中已存在的车辆和行人...")

            actors_to_destroy = []
            for actor in world.get_actors():
                if 'vehicle' in actor.type_id or 'walker' in actor.type_id:
                    actors_to_destroy.append(actor.id)

            if actors_to_destroy:
                print(f"发现并正在销毁 {len(actors_to_destroy)} 个动态 actor...")
                client.apply_batch([carla.command.DestroyActor(x) for x in actors_to_destroy])
                print("✅ 清理完成。")
            else:
                print("✅ 世界是干净的，无需清理。")

        world.tick() # Apply actor changes before creating the camera rig.


        blueprint_library = world.get_blueprint_library()
        os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

        rig_bp = blueprint_library.find('sensor.other.collision')

        initial_transform = carla.Transform(carla.Location(x=0, y=0, z=-100)) # Spawn below the scene until the first trajectory pose is applied.
        camera_rig = world.spawn_actor(rig_bp, initial_transform)
        # Disable physics so the rig follows CSV poses without gravity.
        camera_rig.set_simulate_physics(False)
        actor_list.append(camera_rig)
        print(f'✅ 已创建相机支架 (Actor ID: {camera_rig.id})')


        sensor_definitions = [
            # All six cameras share the rig origin; rotations are relative to the rig.
            {'name': 'front', 'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=0.0, yaw=0.0))},
            {'name': 'back',  'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=0.0, yaw=180.0))},
            {'name': 'left',  'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=0.0, yaw=-90.0))},
            {'name': 'right', 'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=0.0, yaw=90.0))},
            {'name': 'up',    'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=90.0, yaw=0.0))},
            {'name': 'down',  'transform': carla.Transform(carla.Location(x=0.0, z=0.0), carla.Rotation(pitch=-90.0, yaw=0.0))}
        ]

        rgb_camera_bp = blueprint_library.find('sensor.camera.rgb')
        rgb_camera_bp.set_attribute('image_size_x', f'{IMAGE_WIDTH}')
        rgb_camera_bp.set_attribute('image_size_y', f'{IMAGE_HEIGHT}')
        rgb_camera_bp.set_attribute('fov', str(FOV))

        depth_camera_bp = blueprint_library.find('sensor.camera.depth')
        depth_camera_bp.set_attribute('image_size_x', f'{IMAGE_WIDTH}')
        depth_camera_bp.set_attribute('image_size_y', f'{IMAGE_HEIGHT}')
        depth_camera_bp.set_attribute('fov', str(FOV))

        segmentation_camera_bp = blueprint_library.find('sensor.camera.semantic_segmentation')
        segmentation_camera_bp.set_attribute('image_size_x', f'{IMAGE_WIDTH}')
        segmentation_camera_bp.set_attribute('image_size_y', f'{IMAGE_HEIGHT}')
        segmentation_camera_bp.set_attribute('fov', str(FOV))

        sensor_queues = {}
        for definition in sensor_definitions:
            name = definition['name']
            transform = definition['transform']

            if RECORD_RGB:
                rgb_cam = world.spawn_actor(rgb_camera_bp, transform, attach_to=camera_rig)
                actor_list.append(rgb_cam)
                q_rgb = queue.Queue()
                rgb_cam.listen(q_rgb.put)
                sensor_queues[f'rgb_{name}'] = q_rgb

            if RECORD_DEPTH:
                depth_cam = world.spawn_actor(depth_camera_bp, transform, attach_to=camera_rig)
                actor_list.append(depth_cam)
                q_depth = queue.Queue()
                depth_cam.listen(q_depth.put)
                sensor_queues[f'depth_{name}'] = q_depth

            if RECORD_SEGMENTATION:
                seg_cam = world.spawn_actor(segmentation_camera_bp, transform, attach_to=camera_rig)
                actor_list.append(seg_cam)
                q_seg = queue.Queue()
                seg_cam.listen(q_seg.put)
                sensor_queues[f'seg_{name}'] = q_seg


        resumed_trajectory_df = trajectory_df.iloc[start_frame_index:]

        print(f"开始根据轨迹录制数据，总共 {len(trajectory_df)} 帧...")

        if args.dynamic_height:
            progress_bar_desc = f"{folder_name} (动态高度) 的数据录制中"
        else:
            progress_bar_desc = f"{folder_name} 的数据录制中"

        for index, row in tqdm(resumed_trajectory_df.iterrows(),
                        total=len(trajectory_df),
                        initial=start_frame_index,
                        desc=progress_bar_desc):

            # CSV vehicle-trajectory Z; no live ground-height query.
            ground_z = row['z']

            if height_manager:
                current_relative_height = height_manager.get_current_height()
                rig_z = ground_z + current_relative_height
            else:
                rig_z = ground_z + CAMERA_HEIGHT_Z if args.height_mode == 'relative' else CAMERA_HEIGHT_Z

            base_location = carla.Location(x=row['x'], y=row['y'], z=rig_z)
            base_rotation = carla.Rotation(pitch=0.0, yaw=row['yaw'], roll=0.0)
            target_transform = carla.Transform(base_location, base_rotation)

            camera_rig.set_transform(target_transform)

            current_location = camera_rig.get_location()

            is_collided = check_collision_with_ray(world, current_location, 0.4)

            # Match each sensor callback to the tick we just requested.
            simulation_frame = world.tick()
            all_data = {name: receive_frame(q, simulation_frame)
                        for name, q in sensor_queues.items()}

            frame_id_to_save = int(row['frame']) if 'frame' in row else index

            rgb_images = {}
            depth_arrays = {}
            segmentation_tags = {}

            for name, image in all_data.items():
                if name.startswith('rgb_'):
                    view = name.split('_')[1]
                    array = np.frombuffer(image.raw_data, dtype=np.uint8)
                    array = np.reshape(array, (image.height, image.width, 4))
                    rgb_images[view] = array[:, :, :3][:, :, ::-1] # BGR to RGB.
                elif name.startswith('depth_'):
                    view = name.split('_')[1]
                    array = np.frombuffer(image.raw_data, dtype=np.uint8)
                    array = np.reshape(array, (image.height, image.width, 4))
                    normalized_depth = (array[:,:,2].astype(np.float32) + array[:,:,1].astype(np.float32) * 256 + array[:,:,0].astype(np.float32) * 256 * 256) / (256 * 256 * 256 - 1)
                    depth_arrays[view] = normalized_depth * 1000

                elif name.startswith('seg_'):
                    view = name.split('_')[1]
                    array = np.frombuffer(image.raw_data, dtype=np.uint8)
                    array = np.reshape(array, (image.height, image.width, 4))
                    # CARLA stores semantic class IDs in the red channel.
                    tag_array = array[:, :, 2]
                    segmentation_tags[view] = tag_array

            process_and_save_data(frame_id_to_save, rgb_images, depth_arrays,
                                  segmentation_tags, OUTPUT_BASE_DIR, FOV)
            log_line = f"{frame_id_to_save},{row['x']:.4f},{row['y']:.4f},{rig_z:.4f},{row['yaw']:.4f}\n"
            if args.dynamic_height:
                with open(pose_log_path, 'a') as log:
                    log.write(log_line)
            if is_collided:
                with open(log_file_path, 'a') as log:
                    log.write(log_line)
                tqdm.write(f'Collision proximity detected at frame {frame_id_to_save}')

        print("录制结束。")

    finally:
        for actor in actor_list:
            if hasattr(actor, 'stop'):
                try:
                    actor.stop()
                except RuntimeError:
                    pass
        try:
            if client is not None and actor_list:
                client.apply_batch([carla.command.DestroyActor(actor) for actor in actor_list])
        finally:
            if traffic_manager is not None:
                traffic_manager.set_synchronous_mode(False)
            if world is not None and original_settings is not None:
                world.apply_settings(original_settings)
        print('Capture cleanup finished.')


if __name__ == '__main__':
    main()

# Linux: CSV replay and RGB-D panorama capture

English | [简体中文](README.zh-CN.md)

Replay [Stage 1](../stage1/README.md) CSV trajectories, capture six RGB/depth/semantic views, and generate panoramas and inspection videos.

## 1. Environment

Requirements: Conda, an NVIDIA GPU, CARLA 0.9.16, and the map used to record the trajectory.

```bash
conda create -n panocarla-stage2 python=3.11.13 -y
conda activate panocarla-stage2
cd /path/to/PanoCARLA
python -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r stage2/requirements.txt
```

Replace `/path/to/PanoCARLA` with the repository path. Run subsequent commands there with `panocarla-stage2` activated.

The `equilib` projection library is bundled. Install the CARLA simulator and maps separately.

## 2. Start CARLA

From the CARLA installation directory:

```bash
./CarlaUE4.sh -RenderOffScreen -nosound -carla-rpc-port=11536
```

Alternatively, replace `YOUR_CARLA_IMAGE` with your prepared CARLA 0.9.16 Docker image:

```bash
docker run -d \
  --name panocarla_stage2_11536 \
  --gpus 'device=0' \
  --net=host \
  YOUR_CARLA_IMAGE \
  bash ./CarlaUE4.sh \
  -RenderOffScreen -nosound \
  -carla-rpc-port=11536
```

Match `--port` to the server RPC port. Traffic Manager uses `RPC port + 3`; use unique container names and avoid port conflicts between instances.

Run one recorder per CARLA instance. It loads the selected map and enables synchronous mode. Fixed-height and `--no_other_cars` modes remove existing vehicles and walkers.

## 3. Transfer trajectories

Upload checked CSVs to `trajectories/`. Keep `townXX` in filenames for map validation.

```text
trajectories/
├─ first_stage_record_town05_path1_TIMESTAMP.csv
└─ first_stage_record_town05_path2_TIMESTAMP.csv
```

Required columns: `frame,timestamp,x,y,z,pitch,yaw,roll`. Positions are metres and angles are degrees. Frame IDs must be nonnegative, integral and strictly increasing. All CSVs in a batch must use the same map. For Town10, specify `--map Town10HD`.

Replay advances one simulation tick per CSV row without timestamp resampling, so use the Stage 1 FPS (20 by default). Cameras follow CSV x, y and yaw; pitch and roll are held at zero.

## 4. Record six views

Replace the example CSV paths with your files.

### Fixed relative height

```bash
python stage2/run_record_2stage.py \
  --csv_paths trajectories/first_stage_record_town05_path1_TIMESTAMP.csv \
              trajectories/first_stage_record_town05_path2_TIMESTAMP.csv \
  --map Town05 --host localhost --port 11536 \
  --height_mode relative --camera_height 4 \
  --fps 20 --width 800 --height 800 --fov 120 \
  --output_root recordings/town05
```

### Dynamic relative height

```bash
python stage2/run_record_2stage.py \
  --csv_paths trajectories/first_stage_record_town05_path1_TIMESTAMP.csv \
  --map Town05 --host localhost --port 11536 \
  --height_mode relative --camera_height 5 \
  --dynamic_height --min_height 2 --max_height 20 \
  --fps 20 --width 800 --height 800 --fov 120 \
  --output_root recordings/town05
```

| Option/mode | Behavior |
|---|---|
| `--height_mode relative` | World Z = CSV z + offset; this does not remeasure ground clearance |
| `--height_mode absolute` | World Z = `camera_height`; fixed height only |
| `--dynamic_height` | Random smooth transitions, hovering and sinusoidal motion within the bounds; `camera_height` is the initial offset |
| `--vehicle_density 60` | In dynamic mode, attempt vehicle spawning at 60% of map spawn points; no pedestrians are spawned |
| `--no_other_cars` | Do not spawn traffic and remove existing vehicles/walkers; fixed-height mode clears them by default |
| `--dry_run` | Batch command preview without connecting to CARLA |
| `--re_record` | Clear this route's raw sensor files/logs and record from scratch |

All three modalities are captured in six directions. Source images must be square, with an integer FOV in `[90, 180)`.

For a single route, use `record_2stage.py --csv_path ...` with the same capture options. Batches stop on failure.

**Reruns:** complete sequences are skipped. Fixed-height capture resumes at the first incomplete frame; incomplete dynamic sequences have their raw files/logs cleared and are recorded again in full. Changed inputs/settings require a new output directory or `--re_record`. After re-recording, use `--re_stitch` to refresh panoramas and videos.

**Collision annotation:** 0.4 m rays along the six world-axis directions flag nearby obstacles. Flagged frames are retained for inspection.

## 5. Stitch and inspect

Replace `ACTUAL_ROUTE_DIRECTORY` with the capture output directory:

```bash
python stage2/run_stage2_stitch_and_vis.py \
  --base_dirs recordings/town05/ACTUAL_ROUTE_DIRECTORY \
  --original_fov 120 --num_process 4 --fps 20 \
  --equi_height 1200 --equi_width 2400
```

`--base_dirs` accepts multiple directories. Match FOV and FPS to capture settings. Panorama width must be twice its even height. Adjust `--num_process` to available CPU and memory.

Or run the two steps separately:

```bash
python stage2/equi_extract_for_fov100_multiprocess.py \
  --base_dir recordings/town05/ACTUAL_ROUTE_DIRECTORY \
  --original_fov 120 --num_process 4 \
  --equi_height 1200 --equi_width 2400

python stage2/stage2vis_rgbd2video.py \
  --base_dir recordings/town05/ACTUAL_ROUTE_DIRECTORY --fps 20
```

The filename `fov100` does not restrict input FOV; `--original_fov` controls it. RGB-D recordings without semantic labels are supported; if labels are present, all six views are required.

Frame IDs must match across views and modalities. Complete outputs are skipped. After changing dimensions or inputs, use `--re_stitch` to clear and regenerate panoramas. Videos show RGB above depth, with `COLLISION!` and dynamic camera `World Z` annotations.

## 6. Outputs

A route directory uses the CSV stem with its `first_stage_` prefix removed, followed by a mode suffix: `_rz_4.0_fov120` for fixed relative height, or `_rz_dynamic_2.0_20.0_fov120` for dynamic capture, with `_no_car` appended when traffic is disabled.

```text
ROUTE_DIRECTORY/
├─ rgb_{view}_fov120/*.png             RGB
├─ depth_npy_{view}_fov_120/*.npy      Floating-point depth, metres
├─ segmentation_{view}_fov120/*.png   Single-channel semantic IDs
├─ *_collision_log.csv               Flagged frames: frame_id,x,y,z,yaw
├─ *_pose_log.csv                    Per-frame camera poses in dynamic mode
├─ recording_config.json
├─ panorama_rgb/*.png
├─ panorama_depth_npy/*.npy           Panoramic ray distance, metres
├─ panorama_depth_visual/*.png        Colored depth for inspection
├─ panorama_segmentation/*.png
├─ stitch_config.json
└─ *_PanoVideo.mp4                    RGB-over-depth inspection video
```

`view` is `front/back/left/right/up/down`. Filenames retain the CSV frame IDs, padded to at least six digits; numbering does not restart at zero. Use NPY depth for training and colored PNG/MP4 for inspection.

See the [Town15 limitation](../README.md#town15-limitation) for scene-object popping.

## Tests

```bash
python -m unittest discover -s stage2/tests -v
```

Offline tests cover stitching, video generation and data integrity. End-to-end CARLA capture remains unverified.

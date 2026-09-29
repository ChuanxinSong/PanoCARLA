# Windows: trajectory recording

English | [简体中文](README.zh-CN.md)

Plan and record new routes on Windows, then export pose CSV files for the Linux data-capture stage.

## 1. Install and prepare

1. Download and extract the Windows package from the [CARLA 0.9.16 release page](https://github.com/carla-simulator/carla/releases/tag/0.9.16). Install the matching additional maps if needed. CARLA is not bundled with this project.
2. Copy the 11 `.py` scripts in this directory into `CARLA_0.9.16\PythonAPI\user`.
3. Open Anaconda Prompt, create an environment, and install the dependencies:

```bat
conda create -n carla-stage1 python=3.12 -y
conda activate carla-stage1
cd /d D:\CARLA_0.9.16\PythonAPI\user
python -m pip install ..\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl
python -m pip install pygame -r ..\carla\agents\requirements.txt
```

Replace the example path with your CARLA installation path. For later sessions, activate the environment and enter `PythonAPI\user`.

Start CARLA in a separate terminal and keep it running:

```bat
D:\CARLA_0.9.16\CarlaUE4.exe -carla-rpc-port=3346
```

The current `vis_points.py` uses port 3346. All commands below use the same port.

## 2. Plan a new route

**Town15:** We observed trees and other scene objects appearing or disappearing as the viewpoint moved along the trajectory during recording. We did not use or publicly release the recorded Town15 data; its trajectory script is retained for reference only.

```bat
python vis_points.py
```

Select a map when prompted. Use the mouse and WASD in the CARLA window to move to an overhead view and choose a start, intermediate points, and a destination. Yellow numbers identify spawn points; green arrows show their headings.

Move within 10 meters of each spawn point and copy the `carla.Location(...)` and `carla.Rotation(...)` printed in the terminal. When no spawn point is nearby, the output describes the spectator pose instead; do not use it directly as a road point. Press `Ctrl+C` when finished.

## 3. Enter the route and record

Open the script for your town, such as `first_stage_record_town05.py`, and edit a route in `WAYPOINT_PATHS` near the top:

```python
WAYPOINT_PATHS = {
    1: [
        # Insert your selected poses in order:
        # carla.Transform(carla.Location(...), carla.Rotation(...)),
        # Start, intermediate points (optional), destination
    ],
    # Other routes...
}
```

Each route needs at least two points. The first sets the vehicle's spawn position and orientation; subsequent points set target positions. The agent plans the roads between these targets. Add intermediate points on specific road sections to guide the route.

You can edit an existing route. To add a new route ID, also add it to the `choices` list for the `--path` argument near the bottom of the script.

```bat
python first_stage_record_town05.py --map Town05 --path 1 --port 3346
```

`--path 1` selects route 1, not spawn point 1. After the vehicle reaches its destination, the trajectory is saved as:

```text
_out/first_stage_record_town05_path1_TIMESTAMP.csv
```

The scripts default to synchronous recording at 20 FPS. The Town10 script has no `--map` argument; first select `Town10HD` through `vis_points.py`, then run:

```bat
python first_stage_record_town10.py --path 1 --port 3346
```

## 4. Check the trajectory

Specify the recording map and replace the placeholder with your actual CSV filename:

```bat
python vis_trajectory.py --map Town05 --port 3346 _out/YOUR_TRAJECTORY.csv
```

Inspect the trajectory in CARLA to confirm it follows the intended roads and reaches the destination. Adjust the route points and record again if needed. CARLA's autonomous driving does not always follow the intended route, so some fine-tuning of the route points is usually necessary.

CSV columns are `frame,timestamp,x,y,z,pitch,yaw,roll`. Positions are in meters, rotations in degrees, and timestamps in simulation seconds. Transfer the checked CSV to Linux together with its map name, CARLA version, FPS, and route ID.

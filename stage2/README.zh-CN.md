# Linux：沿 CSV 轨迹采集 RGB-D 全景视频

[English](README.md) | 简体中文

回放 [Stage 1](../stage1/README.zh-CN.md) 轨迹 CSV，录制六方向 RGB、深度和语义标签，生成全景图与检查视频。

## 1. 环境准备

需要 Conda、NVIDIA GPU、CARLA 0.9.16 及与轨迹对应的地图。

```bash
conda create -n panocarla-stage2 python=3.11.13 -y
conda activate panocarla-stage2
cd /path/to/PanoCARLA
python -m pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r stage2/requirements.txt
```

将 `/path/to/PanoCARLA` 替换为仓库路径。后续命令均在此目录及 `panocarla-stage2` 环境中运行。

`equilib` 投影库已随附，无需单独安装。CARLA 仿真器和地图需另行安装。

## 2. 启动 CARLA

在 CARLA 安装目录启动：

```bash
./CarlaUE4.sh -RenderOffScreen -nosound -carla-rpc-port=11536
```

或使用 Docker，将 `YOUR_CARLA_IMAGE` 替换为已准备好的 CARLA 0.9.16 镜像：

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

录制 `--port` 必须与 RPC 端口一致。Traffic Manager 使用 `RPC 端口 + 3`；多个实例需使用不同容器名并避免端口冲突。

每个 CARLA 实例只运行一个录制任务。脚本会切换地图、设置同步模式；固定高度或 `--no_other_cars` 模式会清理已有车辆和行人。

## 3. 准备轨迹 CSV

将检查通过的 CSV 上传到 `trajectories/`，文件名保留 `townXX` 以校验地图。

```text
trajectories/
├─ first_stage_record_town05_path1_时间戳.csv
└─ first_stage_record_town05_path2_时间戳.csv
```

CSV 列为 `frame,timestamp,x,y,z,pitch,yaw,roll`，坐标单位米，角度单位度。帧号必须非负、为整数且严格递增。一次批处理中的 CSV 必须来自同一地图。Town10 使用 `--map Town10HD`。

Stage 2 每读取一行 CSV 推进一次仿真，不根据 `timestamp` 重采样。`--fps` 应与 Stage 1 一致，当前默认 20。相机沿 CSV 的 x、y 和 yaw 运动；pitch、roll 固定为 0。

## 4. 录制六方向数据

将示例中的 CSV 路径替换为实际文件。

### 固定相对高度

```bash
python stage2/run_record_2stage.py \
  --csv_paths trajectories/first_stage_record_town05_path1_时间戳.csv \
              trajectories/first_stage_record_town05_path2_时间戳.csv \
  --map Town05 --host localhost --port 11536 \
  --height_mode relative --camera_height 4 \
  --fps 20 --width 800 --height 800 --fov 120 \
  --output_root recordings/town05
```

### 动态相对高度

```bash
python stage2/run_record_2stage.py \
  --csv_paths trajectories/first_stage_record_town05_path1_时间戳.csv \
  --map Town05 --host localhost --port 11536 \
  --height_mode relative --camera_height 5 \
  --dynamic_height --min_height 2 --max_height 20 \
  --fps 20 --width 800 --height 800 --fov 120 \
  --output_root recordings/town05
```

| 参数或模式 | 行为 |
|---|---|
| `--height_mode relative` | 世界 Z = CSV 中的 z + 相对高度；不是重新探测地面的离地高度 |
| `--height_mode absolute` | 世界 Z = `camera_height`，只能使用固定高度 |
| `--dynamic_height` | 在范围内随机切换平滑过渡、悬停和正弦运动；`camera_height` 为初始相对高度 |
| `--vehicle_density 60` | 动态模式尝试在 60% 的地图车辆生成点生成自动驾驶车辆，不生成行人 |
| `--no_other_cars` | 动态模式不生成交通，并清理已有车辆和行人；固定高度模式默认执行清理 |
| `--dry_run` | 批处理仅打印将执行的命令，不连接 CARLA |
| `--re_record` | 清除此路线目录中的原始传感器文件和日志，从头录制 |

三种模态均录制六个方向。源图像须为正方形，FOV 为 `[90, 180)` 内的整数。

单条轨迹可直接调用 `record_2stage.py --csv_path ...`，其余参数相同。批处理遇错停止。

**重跑：**完整序列自动跳过。固定高度从首个不完整帧恢复；动态高度清理未完成序列的原始文件与日志，整条重录。修改输入或参数时，使用新输出目录或 `--re_record`；重录后用 `--re_stitch` 更新全景与视频。

**碰撞标记：**从相机位置沿六个世界坐标轴方向发射 0.4 米射线，记录命中帧并继续采集，用于检查近距离障碍物。

## 5. 拼接全景并生成检查视频

将 `实际路线目录` 替换为录制输出目录：

```bash
python stage2/run_stage2_stitch_and_vis.py \
  --base_dirs recordings/town05/实际路线目录 \
  --original_fov 120 --num_process 4 --fps 20 \
  --equi_height 1200 --equi_width 2400
```

`--base_dirs` 支持多个目录。FOV、FPS 须与录制一致；全景宽度为高度的两倍，高度取偶数。按 CPU 和内存调整 `--num_process`。

也可分别运行：

```bash
python stage2/equi_extract_for_fov100_multiprocess.py \
  --base_dir recordings/town05/实际路线目录 \
  --original_fov 120 --num_process 4 \
  --equi_height 1200 --equi_width 2400

python stage2/stage2vis_rgbd2video.py \
  --base_dir recordings/town05/实际路线目录 --fps 20
```

脚本名中的 `fov100` 不限制输入 FOV，以 `--original_fov` 为准。支持无语义标签的 RGB-D 数据；若有标签，须包含全部六个方向。

各方向、模态的帧号必须一致。完整输出自动跳过；修改尺寸或输入后加 `--re_stitch`，清理并重建全景。视频上方为 RGB，下方为深度，标注 `COLLISION!` 和动态相机的世界坐标 `World Z`。

## 6. 输出结构

录制目录名由 CSV 文件名去掉 `first_stage_` 前缀，再加上模式后缀生成。固定相对高度后缀为 `_rz_4.0_fov120`；动态模式为 `_rz_dynamic_2.0_20.0_fov120`，无交通时再加 `_no_car`。

```text
路线目录/
├─ rgb_{view}_fov120/*.png             RGB
├─ depth_npy_{view}_fov_120/*.npy      浮点深度，米
├─ segmentation_{view}_fov120/*.png   单通道语义类别编号
├─ *_collision_log.csv               命中帧：frame_id,x,y,z,yaw
├─ *_pose_log.csv                    动态模式的逐帧相机位姿
├─ recording_config.json
├─ panorama_rgb/*.png
├─ panorama_depth_npy/*.npy           全景射线距离，米
├─ panorama_depth_visual/*.png        仅用于显示的着色深度
├─ panorama_segmentation/*.png
├─ stitch_config.json
└─ *_PanoVideo.mp4                    RGB 与深度上下拼接的检查视频
```

`view` 为 `front/back/left/right/up/down`。帧文件名使用 CSV 的 `frame`，至少补齐六位，不是重新从 0 编号。训练用深度取 NPY，着色 PNG 和 MP4 用于检查。

Town15 的场景物体闪现问题见[已知限制](../README.zh-CN.md#town15-已知问题)。

## 测试

```bash
python -m unittest discover -s stage2/tests -v
```

离线测试覆盖拼接、视频和数据完整性；CARLA 端到端录制尚未验证。

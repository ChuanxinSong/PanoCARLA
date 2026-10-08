# Windows：轨迹录制

[English](README.md) | 简体中文

在 Windows 上规划并录制新的轨迹，导出 CSV 供 Linux 端第二阶段使用。

## 1. 安装与准备

1. 从 [CARLA 0.9.16 发布页](https://github.com/carla-simulator/carla/releases/tag/0.9.16)下载 Windows 版并解压；需要额外地图时安装同版本附加地图包。CARLA 不随本项目发布。
2. 将本目录的 11 个 `.py` 脚本复制到 `CARLA_0.9.16\PythonAPI\user` 下；
3. 打开 Anaconda Prompt，创建环境并安装依赖：

```bat
conda create -n carla-stage1 python=3.12 -y
conda activate carla-stage1
cd /d D:\CARLA_0.9.16\PythonAPI\user
python -m pip install ..\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl
python -m pip install pygame -r ..\carla\agents\requirements.txt
```

将示例路径替换为自己的 CARLA 安装路径。以后使用时只需激活环境并进入 `PythonAPI\user`。

在另一个终端启动 CARLA，保持仿真器运行：

```bat
D:\CARLA_0.9.16\CarlaUE4.exe -carla-rpc-port=3346
```

当前 `vis_points.py` 使用端口 3346，下面的录制和检查命令也统一使用该端口。

## 2. 规划新路径

**Town15：** 录制时观察到树木等场景物体会随着视点沿轨迹移动而出现或消失。因此，我们没有使用或公开 Town15 的录制数据；对应轨迹脚本仅保留作参考。

```bat
python vis_points.py
```

按提示选择地图，在 CARLA 窗口中用鼠标和 WASD 调整到俯视视角，规划起点、途经点和终点。黄色编号表示生成点，绿色箭头表示朝向。

靠近生成点 10 米内，复制终端显示的 `carla.Location(...)` 和 `carla.Rotation(...)`。不在生成点附近时显示的是观察者自身位姿，不要直接用作道路点。选完后按 `Ctrl+C`。

## 3. 填入路径并录制

打开对应城市脚本，例如 `first_stage_record_town05.py`，修改顶部 `WAYPOINT_PATHS` 中的一条路线：

```python
WAYPOINT_PATHS = {
    1: [
        # 按顺序填入自己选取的位姿：
        # carla.Transform(carla.Location(...), carla.Rotation(...)),
        # 起点、途经点（可多个）、终点
    ],
    # 其他路线……
}
```

每条路线至少两个点。第一个点决定车辆出生位置和朝向，后续点指定目标位置；车辆自动规划点之间的道路路线。希望经过特定路段时，在该路段增加途经点。

可以直接修改已有路线；如果新增路线编号，还需将编号加入脚本底部 `--path` 参数的 `choices`。

```bat
python first_stage_record_town05.py --map Town05 --path 1 --port 3346
```

`--path 1` 选择路线 1，不是地图生成点编号 1。车辆到达终点后，轨迹保存为：

```text
_out/first_stage_record_town05_path1_时间戳.csv
```

当前默认同步录制为 20 FPS。Town10 脚本没有 `--map` 参数，需先通过 `vis_points.py` 选择 `Town10HD`，再运行：

```bat
python first_stage_record_town10.py --path 1 --port 3346
```

## 4. 检查轨迹

指定录制时的地图和实际 CSV 文件名：

```bat
python vis_trajectory.py --map Town05 --port 3346 _out/实际文件名.csv
```

在 CARLA 中检查轨迹是否经过预期道路、到达预期终点。不符合要求则调整路径点重新录制。注意carla的自动驾驶系统没有那么好用，通常需要一些路径点的微调。

CSV 包含 `frame,timestamp,x,y,z,pitch,yaw,roll`。位置单位为米、旋转为度、时间为仿真秒。将检查通过的 CSV 交给 Linux 端，并记录对应地图、CARLA 版本、FPS 和路线编号。

下一步请阅读 [Linux Stage 2 使用说明](../stage2/README.zh-CN.md)，沿 CSV 回放采集 RGB-D 全景数据。

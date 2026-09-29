# PanoCARLA

[English](README.md) | 简体中文

[Hugging Face PanoCARLA 数据集](https://huggingface.co/datasets/Soon122/PanoCARLA)的数据采集代码。

完整流程分为两个阶段：

1. **Windows：轨迹录制。** 自行选择路线点，通过 CARLA 自动驾驶生成车辆位姿 CSV。
2. **Linux：数据采集。** 沿已有轨迹采集数据，当前仓库尚未包含此阶段代码。

## 开始使用

请阅读 [Windows 使用说明](stage1/README.zh-CN.md)，安装 CARLA、配置 Conda 环境并规划自己的路线。

```text
stage1/              Windows 轨迹脚本及中英文说明
licenses/            CARLA 衍生代码的许可证文本
```

CARLA 0.9.16 由用户单独安装。本仓库不包含仿真器、地图、Python wheel、环境或生成数据。命令已按源码核对，尚未完成端到端运行验证。

## Town15 已知问题

我们在 Town15 录制时观察到，树木等场景物体会随着视点沿轨迹移动而出现或消失。因此，我们没有使用或公开 Town15 的录制数据。仓库中的 Town15 轨迹脚本仅保留作参考。

## 许可证

本项目的代码和文档采用 [MIT License](LICENSE)。

轨迹录制脚本基于 CARLA 的自动驾驶示例修改，保留了原有版权声明，详见[第三方声明](THIRD_PARTY_NOTICES.md)。数据集使用条款请查看 Hugging Face 数据集页面。

## 引用

如果您在研究中使用 PanoCARLA，或基于我们的脚本录制数据，请引用 PVDepth 论文：

```bibtex
@inproceedings{song2026pvdepth,
  author    = {Song, Chuanxin and Peng, Peixi},
  title     = {PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation},
  booktitle = {ICML},
  year      = {2026}
}
```

## 致谢

PanoCARLA 使用 [CARLA 0.9.16](https://github.com/carla-simulator/carla) 生成。感谢 CARLA 团队公开提供该仿真器。

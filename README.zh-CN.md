# PanoCARLA

[English](README.md) | 简体中文

本仓库提供 [PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation](https://github.com/ChuanxinSong/PVDepth) 工作所用的 [PanoCARLA 数据集](https://huggingface.co/datasets/Soon122/PanoCARLA)的录制脚本与数据采集细节。同一套流程也用于录制 [PanoCARLA-Static 数据集](https://huggingface.co/datasets/Soon122/PanoCARLA-Static)。

完整流程分为两个阶段：

1. **Windows：轨迹录制。** 自行选择路线点，通过 CARLA 自动驾驶生成车辆位姿 CSV。
2. **Linux：数据采集。** 沿 CSV 轨迹录制六方向 RGB、深度和语义标签，拼接全景图并生成检查视频。

## 开始使用

请阅读 [Windows 使用说明](stage1/README.zh-CN.md)，安装 CARLA、配置 Conda 环境并规划自己的路线。

已有轨迹 CSV 时，继续阅读 [Linux Stage 2 使用说明](stage2/README.zh-CN.md)，在服务器录制并处理全景数据。

```text
stage1/              Windows 轨迹脚本及中英文说明
stage2/              Linux CSV 回放、全景拼接和视频检查
stage2/vendor/       随附的 equilib 投影运行时及许可证
licenses/            CARLA 衍生代码的许可证文本
```

CARLA 0.9.16 由用户单独安装。本仓库不包含仿真器、地图、Python wheel、环境或生成数据。

## Town15 已知问题

我们在 Town15 录制时观察到，树木等场景物体会随着视点沿轨迹移动而出现或消失。因此，我们没有使用或公开 Town15 的录制数据。仓库中的 Town15 轨迹脚本仅保留作参考。

## 许可证

本项目的原创代码和文档采用 [MIT License](LICENSE)。随附的 equilib 运行时采用 Apache-2.0，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

轨迹录制脚本基于 CARLA 的自动驾驶示例修改，保留了原有版权声明，详见[第三方声明](THIRD_PARTY_NOTICES.md)。数据集使用条款请查看各自的 Hugging Face 页面。

## 引用

如果您在研究中使用 PanoCARLA、PanoCARLA-Static 或本仓库的录制脚本，请引用 PVDepth 论文：

```bibtex
@inproceedings{song2026pvdepth,
  author    = {Song, Chuanxin and Peng, Peixi},
  title     = {PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation},
  booktitle = {ICML},
  year      = {2026}
}
```

## 致谢

PanoCARLA 和 PanoCARLA-Static 使用 [CARLA 0.9.16](https://github.com/carla-simulator/carla) 生成。感谢 CARLA 团队公开提供该仿真器。

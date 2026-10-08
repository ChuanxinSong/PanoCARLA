# PanoCARLA

English | [简体中文](README.zh-CN.md)

This repository provides the recording scripts and data collection details for [PanoCARLA](https://huggingface.co/datasets/Soon122/PanoCARLA), the dataset used in [PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation](https://github.com/ChuanxinSong/PVDepth). The same pipeline was also used to record [PanoCARLA-Static](https://huggingface.co/datasets/Soon122/PanoCARLA-Static).

The workflow has two stages:

1. **Windows — trajectory recording:** select route points, drive the route in CARLA, and export vehicle poses to CSV.
2. **Linux — data capture:** replay CSV trajectories to record six RGB/depth/semantic views, stitch panoramas, and create inspection videos.

## Get started

See the [Windows guide](stage1/README.md) to install CARLA, set up a Conda environment, and plan your own routes.

If you already have trajectory CSVs, continue with the [Linux Stage 2 guide](stage2/README.md) to capture and process panoramic data on a server.

```text
stage1/              Windows trajectory scripts and bilingual instructions
stage2/              Linux CSV replay, panorama stitching and video inspection
stage2/vendor/       Bundled equilib projection runtime and license
licenses/            License text for CARLA-derived code
```

CARLA 0.9.16 is installed separately. Simulator binaries, maps, Python wheels, environments, and generated data are not included.

## Town15 limitation

During our Town15 recordings, trees and other scene objects appeared or disappeared as the viewpoint moved along the trajectory. We therefore did not use or publicly release the recorded Town15 data. The Town15 trajectory script is retained for reference.

## License

This project's original code and documentation are released under the [MIT License](LICENSE). The bundled equilib runtime uses Apache-2.0; see [third-party notices](THIRD_PARTY_NOTICES.md).

The trajectory recording scripts are adapted from CARLA's automatic-control example and retain their original copyright notices. See [third-party notices](THIRD_PARTY_NOTICES.md). Dataset terms are provided on the respective Hugging Face dataset pages.

## Citation

If you use PanoCARLA, PanoCARLA-Static, or these recording scripts in your research, please cite the PVDepth paper:

```bibtex
@inproceedings{song2026pvdepth,
  author    = {Song, Chuanxin and Peng, Peixi},
  title     = {PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation},
  booktitle = {ICML},
  year      = {2026}
}
```

## Acknowledgements

PanoCARLA and PanoCARLA-Static were generated with [CARLA 0.9.16](https://github.com/carla-simulator/carla). We thank the CARLA team for making the simulator publicly available.

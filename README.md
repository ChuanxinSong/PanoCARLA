# PanoCARLA

English | [简体中文](README.zh-CN.md)

Data collection code for [PanoCARLA on Hugging Face](https://huggingface.co/datasets/Soon122/PanoCARLA).

The workflow has two stages:

1. **Windows — trajectory recording:** select route points, drive the route in CARLA, and export vehicle poses to CSV.
2. **Linux — data capture:** use the recorded trajectories to collect data. This stage is not included yet.

## Get started

See the [Windows guide](stage1/README.md) to install CARLA, set up a Conda environment, and plan your own routes.

```text
stage1/              Windows trajectory scripts and bilingual instructions
licenses/            License text for CARLA-derived code
```

CARLA 0.9.16 is installed separately. Simulator binaries, maps, Python wheels, environments, and generated data are not included. Commands have been checked against the source; end-to-end validation is pending.

## Town15 limitation

During our Town15 recordings, trees and other scene objects appeared or disappeared as the viewpoint moved along the trajectory. We therefore did not use or publicly release the recorded Town15 data. The Town15 trajectory script is retained for reference.

## License

This project's code and documentation are released under the [MIT License](LICENSE).

The trajectory recording scripts are adapted from CARLA's automatic-control example and retain their original copyright notices. See [third-party notices](THIRD_PARTY_NOTICES.md). Dataset terms are provided on the Hugging Face dataset page.

## Citation

If you use PanoCARLA or collect data using our scripts in your research, please cite the PVDepth paper:

```bibtex
@inproceedings{song2026pvdepth,
  author    = {Song, Chuanxin and Peng, Peixi},
  title     = {PVDepth: Panoramic Video Depth Estimation via Geometry-Aware Spatiotemporal Adaptation},
  booktitle = {ICML},
  year      = {2026}
}
```

## Acknowledgements

PanoCARLA was generated with [CARLA 0.9.16](https://github.com/carla-simulator/carla). We thank the CARLA team for making the simulator publicly available.

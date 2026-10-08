# Third-party notices

The `stage1/first_stage_record_town*.py` scripts are adapted from CARLA's automatic-control example. Their original headers credit Intel Labs (2018) and German Ros and identify the MIT license.

The upstream CARLA license text is preserved in [licenses/CARLA-MIT.txt](licenses/CARLA-MIT.txt). Original source headers are retained unchanged.

CARLA itself, including the `agents` navigation package, is an external dependency and is not bundled here. This notice does not assign a license to the dataset or to unrelated project material.

## equilib

`stage2/vendor/equilib/equilib/` contains an unchanged copy of the Python runtime
from the local equilib checkout used by the original processing pipeline,
including its `pers2equi` implementation. The declared version is 0.5.8 and the
local checkout commit is `ff7268034068321776b85f419738ac47b5724e96`.

Upstream: [haruishi43/equilib](https://github.com/haruishi43/equilib), authored by
Haruya Ishikawa. Its Apache-2.0 license is retained in
[stage2/vendor/equilib/LICENSE](stage2/vendor/equilib/LICENSE). This third-party
runtime is not relicensed under the repository's MIT license.

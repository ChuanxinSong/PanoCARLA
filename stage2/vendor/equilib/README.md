# Bundled equilib runtime

This directory contains the Python runtime from the local `equilib` checkout used
by the original PanoCARLA processing scripts, including `pers2equi`.

- Upstream: https://github.com/haruishi43/equilib
- Local checkout commit: `ff7268034068321776b85f419738ac47b5724e96`
- Declared version: `0.5.8`
- License: Apache-2.0; full text in [LICENSE](LICENSE).

The runtime files are copied unchanged. Development tools, examples, generated
data and package metadata are excluded. The stitching script explicitly imports
this bundled copy so its projection implementation does not depend on a separate
system installation of `pyequilib`. NumPy and PyTorch are installed separately.

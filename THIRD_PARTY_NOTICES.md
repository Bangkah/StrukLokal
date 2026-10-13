# Third-party software notices

StrukLokal is distributed under the MIT License; see [LICENSE](LICENSE). This file records direct Python packages observed in the development environment on 2026-10-14. `requirements.txt` specifies compatible version ranges for most packages, so an installation may resolve different versions.

| Package | Observed version | License reported by package metadata | Upstream project |
| --- | ---: | --- | --- |
| Flask | 3.1.3 | BSD-3-Clause | [Pallets / Flask](https://github.com/pallets/flask) |
| Pillow | 12.3.0 | MIT-CMU | [python-pillow/Pillow](https://github.com/python-pillow/Pillow) |
| NumPy | 1.26.4 | BSD-3-Clause; distribution includes separately licensed components | [numpy/numpy](https://github.com/numpy/numpy) |
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0, and dependency licenses | [pypdfium2-team/pypdfium2](https://github.com/pypdfium2-team/pypdfium2) |
| PaddleOCR | 3.7.0 | Apache-2.0 | [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| PaddlePaddle | 3.2.0 | Apache-2.0 | [PaddlePaddle/Paddle](https://github.com/PaddlePaddle/Paddle) |

The versions above describe the development environment, not a lockfile or a guarantee about every installation. Refer to each exact distribution's license and bundled-notice files when redistributing that distribution. In particular, NumPy and pypdfium2 include or depend on other components with their own notices.

PaddleOCR may download model weights separately at setup or first use. The model artifacts and their licenses have not been inventoried here. Verify the specific model files and their terms before packaging or redistributing them.

This notice is a starting point for review. It does not enumerate all transitive Python dependencies, native libraries, or model artifacts installed on a machine.

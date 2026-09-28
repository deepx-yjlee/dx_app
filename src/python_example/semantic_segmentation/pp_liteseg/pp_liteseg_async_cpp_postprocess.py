#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""pp_liteseg async_cpp_postprocess inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python pp_liteseg_async_cpp_postprocess.py --variant pp-liteseg-stdc1-camvid-10k_960x720
"""
import sys
from pathlib import Path

_script = Path(__file__).resolve()
# Vendored ./common (extract layout) wins; otherwise walk up to src/python_example.
_script_dir = _script.parent
for _cursor in (_script_dir, *_script_dir.parents):
    if (_cursor / "common" / "runner" / "entry.py").is_file():
        if str(_cursor) not in sys.path:
            sys.path.insert(0, str(_cursor))
        break

from common.runner.entry import install_import_paths, run_entry

install_import_paths(_script)

from factory import PpLitesegFactory
from common.runner import AsyncRunner


def main():
    run_entry(
        _script,
        factory_cls=PpLitesegFactory,
        runner_cls=AsyncRunner,
        description="pp_liteseg async_cpp_postprocess inference",
    )


if __name__ == "__main__":
    main()

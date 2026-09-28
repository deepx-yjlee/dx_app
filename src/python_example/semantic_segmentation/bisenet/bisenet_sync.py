#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""bisenet sync inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python bisenet_sync.py --variant bisenetv1_1024x2048
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

from factory import BisenetFactory
from common.runner import SyncRunner


def main():
    run_entry(
        _script,
        factory_cls=BisenetFactory,
        runner_cls=SyncRunner,
        description="bisenet sync inference",
    )


if __name__ == "__main__":
    main()

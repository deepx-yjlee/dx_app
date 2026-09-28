#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""yolo26_seg sync inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python yolo26_seg_sync.py --variant yolo26-l-seg_640x640
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

from factory import Yolo26SegFactory
from common.runner import SyncRunner


def main():
    run_entry(
        _script,
        factory_cls=Yolo26SegFactory,
        runner_cls=SyncRunner,
        description="yolo26_seg sync inference",
    )


if __name__ == "__main__":
    main()

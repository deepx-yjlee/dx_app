#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""mnasnet sync_cpp_postprocess inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python mnasnet_sync_cpp_postprocess.py --variant mnasnet-0.5_224x224
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

from factory import MnasnetFactory
from common.runner import SyncRunner


def main():
    run_entry(
        _script,
        factory_cls=MnasnetFactory,
        runner_cls=SyncRunner,
        description="mnasnet sync_cpp_postprocess inference",
    )


if __name__ == "__main__":
    main()

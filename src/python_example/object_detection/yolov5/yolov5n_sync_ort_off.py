#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""
Yolov5 Synchronous Inference Example

Usage:
    python yolov5n_sync_ort_off.py --model model.dxnn --image input.jpg
"""

import sys
from pathlib import Path

_module_dir = Path(__file__).resolve().parent
_v3_dir = _module_dir.parent.parent
for _path in [str(_v3_dir), str(_module_dir)]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# The family directory has no factory/ of its own; this script runs the registry
# variant of the model it is named after, whose directory holds the factory.
from common.runner.entry import ort_off_variant_dir  # noqa: E402

sys.path.insert(0, str(ort_off_variant_dir(__file__)))

from factory import Yolov5Factory
from common.runner import SyncRunner, parse_common_args

def parse_args():
    return parse_common_args("YOLOv5n Sync Inference")
def main():
    args = parse_args()
    factory = Yolov5Factory()
    runner = SyncRunner(factory, use_ort=False)
    runner.run(args)

if __name__ == "__main__":
    main()

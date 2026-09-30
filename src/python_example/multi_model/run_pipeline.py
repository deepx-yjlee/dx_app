#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Run one multi-model pipeline JSON file.

    python run_pipeline.py --pipeline hand_cascade/pipeline.json --image sample.jpg
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

_SCRIPT_DIR = Path(__file__).resolve().parent
for _cursor in (_SCRIPT_DIR, *_SCRIPT_DIR.parents):
    if (_cursor / "common" / "runner" / "entry.py").is_file():
        if str(_cursor) not in sys.path:
            sys.path.insert(0, str(_cursor))
        break

from common.multi import MultiModelRunner  # noqa: E402


def main() -> None:
    """Load a pipeline file and run it on one image."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run a multi-model pipeline JSON file")
    parser.add_argument("--pipeline", required=True, help="Path to pipeline.json")
    parser.add_argument("--image", required=True, help="BGR image to run")
    parser.add_argument("--models-dir", default=None, help="Directory of .dxnn files")
    parser.add_argument("--save", default=None, help="Optional path for a copy of the input image")
    args = parser.parse_args()

    image_path = Path(args.image)
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise SystemExit(f"cannot read image {image_path}")

    models_dir = Path(args.models_dir) if args.models_dir else None
    runner = MultiModelRunner.from_json(args.pipeline, models_dir)
    result = runner.run_frame(frame)
    logging.getLogger(__name__).info("%s %s", runner.factory.get_model_name(), result.fused)
    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(save_path), frame):
            raise SystemExit(f"cannot write {save_path}")


if __name__ == "__main__":
    main()

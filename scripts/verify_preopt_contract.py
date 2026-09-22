#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Verify the pre-optimized output contract against real hardware.

63 of the 147 DX Model Zoo 2_5_0 additions are pre-optimized YOLO models, and none of
their .dxnn files is published yet (every URL returns 403). Their postprocessing is
still verifiable, because the contract is shared: all 30 detection variants produce
the same [1, K, 6] row table, all 15 pose variants the same [1, K, 57], all 18
segmentation variants the same [1, K, 38] plus prototypes -- and dx_yolo26 ships one
real .dxnn for each of the three.

So this script is the hardware evidence for that whole group. It runs each model on
the NPU through the shipped preprocessor and the new postprocessor and asserts:

  * the output really is the table this decode assumes, at the expected width,
  * the decode yields detections on a real photograph,
  * every box lies inside the original frame.

It is a script rather than a unit test because tests/python_example/conftest.py
installs a Mock for dx_engine during pytest_configure -- correct for unit tests, fatal
for a hardware one. tests/python_example/test_preopt_contract.py drives this as a
subprocess under the existing `e2e` marker.

Usage:
    python3 scripts/verify_preopt_contract.py
    python3 scripts/verify_preopt_contract.py --models-dir /path/to/preopt/models
    python3 scripts/verify_preopt_contract.py --image sample/img/sample_people.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python_example"))

DEFAULT_MODELS_DIR = Path("/home/yjlee/git-src/dx_yolo26/models")

# (file stem, postprocessor class name, expected row width, config, sample image)
#
# The image is per case, matching the runner's own task defaults: a pose model detects
# people and nothing else, so running it on the street scene legitimately returns zero
# results and would make this script report a failure that is not one. (Measured: the
# street image yields 0 poses, sample_people.jpg yields 2 at score 0.95 / 0.92.)
CASES = (
    ("pre_optimized_yolo26-n-od", "PreoptDetectionPostprocessor", 6, {},
     "sample/img/sample_street.jpg"),
    ("pre_optimized_yolo26n-pose", "PreoptPosePostprocessor", 57, {"num_keypoints": 17},
     "sample/img/sample_people.jpg"),
    ("pre_optimized_yolo26n-seg", "PreoptSegPostprocessor", 38, {"num_mask_coefs": 32},
     "sample/img/sample_street.jpg"),
)


def _shapes(tensors) -> str:
    return ", ".join("(" + ", ".join(str(d) for d in t.shape) + ")" for t in tensors)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR,
                    help=f"directory holding the pre-optimized .dxnn files "
                         f"(default: {DEFAULT_MODELS_DIR})")
    ap.add_argument("--image", type=Path, default=None,
                    help="override the per-case sample image (see CASES)")
    ap.add_argument("--score-threshold", type=float, default=0.3)
    ap.add_argument("--nms-threshold", type=float, default=0.45)
    args = ap.parse_args()

    if not args.models_dir.is_dir():
        print(f"[DXAPP] [ERROR] models dir not found: {args.models_dir}\n"
              "        Pass --models-dir, or clone dx_yolo26 which ships the three "
              "pre-optimized models.", file=sys.stderr)
        return 2

    import cv2
    from dx_engine import InferenceEngine

    from common import processors as procs

    failures: list[str] = []
    for stem, class_name, cols, extra, default_image in CASES:
        model_path = args.models_dir / f"{stem}.dxnn"
        if not model_path.is_file():
            failures.append(f"{stem}: model missing at {model_path}")
            continue

        image_path = args.image or (ROOT / default_image)
        frame = cv2.imread(str(image_path))
        if frame is None:
            failures.append(f"{stem}: cannot read image {image_path}")
            continue

        tensor, ctx = procs.LetterboxPreprocessor(640, 640).process(frame)
        outputs = list(InferenceEngine(str(model_path)).run([tensor]))
        print(f"\n[DXAPP] [INFO] {stem}")
        print(f"        image:   {image_path.name} "
              f"{frame.shape[1]}x{frame.shape[0]}")
        print(f"        outputs: {_shapes(outputs)}")

        table = next((o for o in outputs
                      if o.ndim == 3 and o.shape[0] == 1
                      and o.shape[1] > o.shape[2] >= 6), None)
        if table is None:
            failures.append(f"{stem}: no row table among {_shapes(outputs)}")
            continue
        if table.shape[2] != cols:
            failures.append(
                f"{stem}: row width {table.shape[2]}, expected {cols} -- the "
                "pre-optimized contract has changed and the design spec is now wrong")
            continue
        print(f"        row table: {table.shape}  (contract: [1, K, {cols}]) OK")

        config = {"score_threshold": args.score_threshold,
                  "nms_threshold": args.nms_threshold, **extra}
        results = getattr(procs, class_name)(640, 640, config).process(outputs, ctx)
        print(f"        {class_name}: {len(results)} result(s)")
        if not results:
            failures.append(f"{stem}: decode produced no results on {image_path.name}")
            continue

        for result in results[:3]:
            box = [round(v, 1) for v in result.box]
            detail = ""
            if hasattr(result, "keypoints") and result.keypoints:
                detail = f"  keypoints={len(result.keypoints)}"
            if getattr(result, "mask", None) is not None and getattr(result.mask, "size", 0):
                detail = f"  mask={result.mask.shape} dtype={result.mask.dtype}"
            print(f"          class={result.class_id:<3} "
                  f"score={result.confidence:.3f}  box={box}{detail}")

        out_of_frame = [
            r.box for r in results
            if not (0.0 <= r.box[0] <= r.box[2] <= frame.shape[1]
                    and 0.0 <= r.box[1] <= r.box[3] <= frame.shape[0])
        ]
        if out_of_frame:
            failures.append(f"{stem}: {len(out_of_frame)} box(es) outside the frame, "
                            f"e.g. {out_of_frame[0]}")

    print()
    if failures:
        for line in failures:
            print(f"[DXAPP] [ERROR] {line}", file=sys.stderr)
        print(f"[DXAPP] [ERROR] RESULT: FAIL ({len(failures)} problem(s))",
              file=sys.stderr)
        return 1
    print(f"[DXAPP] [INFO] RESULT: PASS -- {len(CASES)}/{len(CASES)} pre-optimized "
          "contracts verified on the NPU")
    return 0


if __name__ == "__main__":
    sys.exit(main())

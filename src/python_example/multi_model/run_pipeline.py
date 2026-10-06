#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""Run one multi-model pipeline JSON file on one image or one video.

    python run_pipeline.py --pipeline hand_cascade/pipeline.json --image sample.jpg
    python run_pipeline.py --pipeline hand_cascade/pipeline.json --video clip.mp4 --frames 8
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
from common.multi.pipeline import PipelineError  # noqa: E402

logger = logging.getLogger(__name__)

_VIDEO_SUFFIXES = (".mp4", ".avi", ".mkv", ".mov")
_MIN_WRITER_FPS = 1.0
_MAX_WRITER_FPS = 240.0
_DEFAULT_WRITER_FPS = 30.0


def _positive_frames(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--frames needs a positive integer") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("--frames must be at least 1")
    return value


def _writer_fps(reported: float) -> float:
    if reported < _MIN_WRITER_FPS or reported > _MAX_WRITER_FPS:
        return _DEFAULT_WRITER_FPS
    return reported


def _run_image(runner: MultiModelRunner, frame, save: str | None) -> None:
    result = runner.run_frame(frame)
    logger.info("%s %s", runner.factory.get_model_name(), result.fused)
    if not save:
        return
    save_path = Path(save)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(save_path), frame):
        raise SystemExit(f"cannot write {save_path}")


def _open_writer(save_path: Path, capture: cv2.VideoCapture, frame) -> cv2.VideoWriter:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc_name = "MJPG" if save_path.suffix.lower() == ".avi" else "mp4v"
    fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
    height, width = frame.shape[:2]
    writer = cv2.VideoWriter(
        str(save_path), fourcc, _writer_fps(float(capture.get(cv2.CAP_PROP_FPS))), (width, height)
    )
    if not writer.isOpened():
        raise SystemExit(f"cannot write {save_path}")
    return writer


def _run_video(runner: MultiModelRunner, capture: cv2.VideoCapture, video_path: Path,
               frame_limit: int | None, save_path: Path | None) -> None:
    writer = None
    index = 0
    try:
        while frame_limit is None or index < frame_limit:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if save_path is not None and writer is None:
                writer = _open_writer(save_path, capture, frame)
            result = runner.run_frame(frame)
            logger.info("frame %d: %s", index, result.fused)
            if writer is not None:
                writer.write(frame)
            index += 1
    finally:
        capture.release()
        if writer is not None:
            writer.release()
    if index == 0:
        raise SystemExit(f"cannot read video {video_path}")
    logger.info("%d frame%s", index, "" if index == 1 else "s")


def main() -> None:
    """Load a pipeline file and run it on one image or one video."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run a multi-model pipeline JSON file")
    parser.add_argument("--pipeline", required=True, help="Path to pipeline.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", help="BGR image to run")
    source.add_argument("--video", help="Video file to run, one frame at a time")
    parser.add_argument("--frames", type=_positive_frames, default=None,
                        help="Stop --video after N frames (default: all)")
    parser.add_argument("--models-dir", default=None, help="Directory of .dxnn files")
    parser.add_argument("--save", default=None,
                        help="Copy of the image, or a .mp4/.avi/.mkv/.mov of the video frames")
    args = parser.parse_args()
    if args.frames is not None and not args.video:
        parser.error("--frames applies to --video")

    save_path = Path(args.save) if args.save else None
    if args.video and save_path is not None and save_path.suffix.lower() not in _VIDEO_SUFFIXES:
        parser.error("--save with --video needs a .mp4, .avi, .mkv or .mov path")

    frame = None  # decoded BGR image when --image is set
    capture = None  # open video when --video is set
    if args.image:
        frame = cv2.imread(str(args.image))
        if frame is None:
            raise SystemExit(f"cannot read image {args.image}")
    else:
        capture = cv2.VideoCapture(str(args.video))
        if not capture.isOpened():
            capture.release()
            raise SystemExit(f"cannot read video {args.video}")

    models_dir = Path(args.models_dir) if args.models_dir else None
    try:
        runner = MultiModelRunner.from_json(args.pipeline, models_dir)
        if capture is not None:
            _run_video(runner, capture, Path(args.video), args.frames, save_path)
            capture = None
        else:
            _run_image(runner, frame, args.save)
    except PipelineError as exc:
        raise SystemExit(f"[DXAPP] [ERROR] {exc}") from None
    finally:
        if capture is not None:
            capture.release()


if __name__ == "__main__":
    main()

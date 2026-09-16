#!/usr/bin/env python3
# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""espcn async_cpp_postprocess inference.

One entry point serves the whole family; ``--variant`` picks the model::

    python espcn_async_cpp_postprocess.py --variant espcn-x2_17x17
"""
import sys
from pathlib import Path

_module_dir = Path(__file__).parent
_v3_dir = _module_dir.parent.parent
for _path in [str(_v3_dir), str(_module_dir)]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from factory import EspcnFactory
from common.runner import AsyncRunner, parse_common_args
from common.variant_config import default_variant, load_variant_config

_VARIANTS_DIR = str(_module_dir / "variants")


def _peek_variant(argv):
    """Read --variant before argparse runs.

    The parser's SHAPE depends on the variant: an image-only variant must not register
    --video/--camera/--rtsp at all, and some variants add --output or the KITTI
    companion paths. So the variant has to be known before the parser is built.
    """
    for i, a in enumerate(argv):
        if a == "--variant" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--variant="):
            return a.split("=", 1)[1]
    return None


def main():
    variant = _peek_variant(sys.argv[1:]) or default_variant(_VARIANTS_DIR)
    cli = load_variant_config(_VARIANTS_DIR, variant).get("cli") or {}
    args = parse_common_args(
        "espcn async_cpp_postprocess inference",
        include_stream_inputs=cli.get("include_stream_inputs", True),
        include_output=cli.get("include_output", False),
        include_kitti_paths=cli.get("include_kitti_paths", False),
    )
    factory = EspcnFactory(variant=variant)
    AsyncRunner(factory).run(args)


if __name__ == "__main__":
    main()

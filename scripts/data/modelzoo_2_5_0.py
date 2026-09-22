# Copyright (C) 2018- DEEPX Ltd. All rights reserved.
"""The 147 DX Model Zoo additions that dx-modelzoo has not published yet.

This module is DATA. It is the single source for every generated artifact:
``config/model_registry.json`` entries, ``tests/data/processor_specs.json`` entries,
the ``provisional`` section of ``tests/data/modelzoo_cv_tree.json`` and the
``scripts/modelzoo_manifest.json`` rows. Change a family name here and re-run
``scripts/add_modelzoo_2_5_0_models.py`` -- never edit the generated files.

Why "provisional": dx-modelzoo assigns ``(task, family)`` as DATA, and for these 147
that data does not exist yet (harvested 2026-09-22: 350 variants, zero overlap with
this list). The names below follow dx-modelzoo's own rule, read from the repo: the
family boundary is the POSTPROCESSING CHAIN.

    yolov8-s_640x640         family yolov8     postprocessing: yolov8_decode, nms
    yolov8-s_640x640_decode  family yolov8     postprocessing: yolov8_decode, nms
    yolov8-n_640x640_ppu     family yolo-ppu   postprocessing: ppu_nms

A different *compiled output* of the same architecture with the same postprocessing
stays in the architecture family (``_decode``); a different *postprocessing mechanism*
gets its own family, even though ``yolov8-n_640x640_ppu`` shares weights with
``yolov8-n_640x640`` (``yolo-ppu`` holds v3/v4/v5/v7/v8/v9/v10/11/v12/x side by side).
Pre-optimized models carry a wholly different chain -- a top-k row table, no dense
decode, no standard NMS -- so they get mechanism families: ``yolo_preopt``,
``yolo_preopt_pose``, ``yolo_preopt_seg``.

dx_app renders dx-modelzoo's ``-`` as ``_`` in directory and registry ``family``
values, as it already does for ``yolo-ppu`` -> ``yolo_ppu`` and ``stdc-seg`` ->
``stdc_seg``.
"""
from __future__ import annotations

import re

try:
    from data.modelzoo_2_5_0_zoo_rows import ZOO_ROWS
except ImportError:  # run directly as scripts/data/modelzoo_2_5_0.py
    from modelzoo_2_5_0_zoo_rows import ZOO_ROWS

# --------------------------------------------------------------------- geometry

# The zoo resolution column uses two spellings, both verified against the 349
# published rows: HxWxC (341 rows, e.g. 224x224x3, 1024x2048x3) and WxCxH (8 rows
# whose MIDDLE token is the channel count, e.g. 1280x3x736 --
# retinaface_mobilenetv1_736x1280 pins that reading: registry w=1280 h=736).
#
# The .dxnn stem's own axis order is NOT consistent -- it inherits whatever the
# upstream repo called it (PaddleSeg's pp-liteseg 960x720 is WxH, MMSeg's
# stdc1-seg50 512x1024 is HxW) -- so the normalised column is the source, not the stem.
_GEOMETRY_EXCEPTIONS = {
    # The zoo transposed this row. Its own vitpose-s_256x192 row says 256x192x3
    # (w=192, h=256, and the registry agrees), while dark_hrnet_w32_256x192 says
    # 192x256x3. Both are MMPose top-down person crops at H=256, W=192 -- portrait --
    # so the dark-hrnet row is the typo. Following it would feed the model a
    # landscape tensor and silently wreck every keypoint.
    "dark-hrnet-w32_256x192": (192, 256),
    # Not an image. The .dxnn takes [1, 77, 512] CLIP token embeddings, and
    # CLIPTextPostprocessor documents its own axes as input_width=77 (token length),
    # input_height=512 (embedding width). Keep the class's convention.
    "clip-text_resnet50_77x512_openai": (77, 512),
}


def resolution(variant: str) -> tuple[int, int]:
    """``(width, height)`` for *variant*, from the zoo's normalised column."""
    if variant in _GEOMETRY_EXCEPTIONS:
        return _GEOMETRY_EXCEPTIONS[variant]
    parts = [int(p) for p in re.findall(r"\d+", ZOO_ROWS[variant][1])]
    if len(parts) == 3 and parts[1] == 3 and parts[0] != 3:
        return parts[0], parts[2]           # W x C x H
    if len(parts) == 3:
        return parts[1], parts[0]           # H x W x C
    if len(parts) == 2:
        return parts[1], parts[0]           # H x W
    raise ValueError(f"{variant}: cannot read resolution {ZOO_ROWS[variant][1]!r}")


# --------------------------------------------------------------------- spec shapes

WH = [{"token": "input_width"}, {"token": "input_height"}]
WHC = WH + [{"token": "config"}]


def _proc(cls: str, args: list, **kwargs) -> dict:
    return {"class": cls, "args": args, "kwargs": kwargs, "config_overrides": {}}


LETTERBOX = _proc("LetterboxPreprocessor", WH)
SIMPLE = _proc("SimpleResizePreprocessor", WH)

# open_clip's canonical normalisation. SimpleResizePreprocessor applies mean/std to the
# RAW 0-255 resized image, so the [0,1] constants are pre-multiplied here; the two forms
# are algebraically identical, (v - 255m) / 255s == (v/255 - m) / s. The existing clip
# family carries the same constants in custom_ops.py, where its measurement is recorded:
# against host FP32 over 21 images, x/255 scored p5 cosine 0.4724 / mean 0.7901 and these
# constants 0.8350 / 0.8935. Getting this wrong relocates image embeddings into a
# different space from host-encoded text and degrades retrieval without ever erroring.
CLIP_SIMPLE = _proc(
    "SimpleResizePreprocessor", WH,
    mean=[0.48145466 * 255.0, 0.4578275 * 255.0, 0.40821073 * 255.0],
    std=[0.26862954 * 255.0, 0.26130258 * 255.0, 0.27577711 * 255.0],
)

# Manifest 'category' follows the legacy task spelling the existing 352 rows use.
MANIFEST_CATEGORY = {
    "object_detection": "Object Detection",
    "instance_segmentation": "Instance Segmentation",
    "pose_estimation": "Pose Estimation",
    "classification": "Classification",
    "reid": "Classification",
    "semantic_segmentation": "Semantic Segmentation",
    "embedding": "Embedding",
    "super_resolution": "Super Resolution",
    "anomaly_detection": "Anomaly Detection",
}

# Upstream references. The zoo leaves the Source column empty for all 143 new rows.
REF_ULTRALYTICS = "https://github.com/ultralytics/ultralytics"
REF_YOLOV9 = "https://github.com/WongKinYiu/yolov9"
REF_YOLOV12 = "https://github.com/sunsmarterjie/yolov12"
REF_YOLOV13 = "https://github.com/iMoonLab/yolov13"
REF_YOLOV6 = "https://github.com/meituan/YOLOv6"
REF_PADDLEDET = "https://github.com/PaddlePaddle/PaddleDetection"
REF_PADDLECLAS = "https://github.com/PaddlePaddle/PaddleClas"
REF_PADDLESEG = "https://github.com/PaddlePaddle/PaddleSeg"
REF_DDRNET = "https://github.com/ydhongHIT/DDRNet"
REF_STDC = "https://github.com/MichaelFan01/STDC-Seg"
REF_EFFICIENTAD = "https://github.com/amazon-science/efficient-ad"
REF_PATCHCORE = "https://github.com/amazon-science/patchcore-inspection"
REF_CLIP = "https://github.com/openai/CLIP"
REF_METACLIP = "https://github.com/facebookresearch/MetaCLIP"
REF_SWIN = "https://github.com/microsoft/Swin-Transformer"
REF_VIT = "https://github.com/google-research/vision_transformer"
REF_TORCHVISION = "https://github.com/pytorch/vision"
REF_HRNET = "https://github.com/HRNet/HigherHRNet-Human-Pose-Estimation"

_SIZES = ("n", "s", "m", "l", "x")


def _preopt(arch: str, sizes, infix: str = "") -> list[str]:
    return [f"{arch}-{s}{infix}_640x640_pre-optimized" for s in sizes]


def _plain(arch: str, sizes, infix: str = "", res: str = "640x640") -> list[str]:
    return [f"{arch}-{s}{infix}_{res}" for s in sizes]


# --------------------------------------------------------------------- the table
#
# Every group states its own task, family, processors and factory base. Nothing is
# inferred from the task at emit time: image_classification alone mixes
# IClassificationFactory and IEmbeddingFactory, so a per-task lookup would silently
# re-base a family.

GROUPS: list[dict] = [
    # ============================ pre-optimized (63) ============================
    dict(
        task="object_detection", task_legacy="object_detection", family="yolo_preopt",
        variants=(_preopt("yolo11", _SIZES) + _preopt("yolo26", _SIZES)
                  + _preopt("yolov8", _SIZES) + _preopt("yolov12", _SIZES)
                  + _preopt("yolov13", ("n", "s", "l", "x"))
                  + _preopt("yolov9", ("t", "s", "m", "c", "e", "gelan-c"))),
        preprocessor=LETTERBOX,
        postprocessor=_proc("PreoptDetectionPostprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_ULTRALYTICS,
        config={"score_threshold": 0.3, "nms_threshold": 0.45, "top_k": 300},
    ),
    dict(
        task="pose_estimation", task_legacy="pose_estimation", family="yolo_preopt_pose",
        variants=(_preopt("yolo11", _SIZES, "-pose") + _preopt("yolo26", _SIZES, "-pose")
                  + _preopt("yolov8", _SIZES, "-pose")),
        preprocessor=LETTERBOX,
        postprocessor=_proc("PreoptPosePostprocessor", WHC),
        visualizer=_proc("PoseVisualizer", []),
        base="IPoseFactory", reference=REF_ULTRALYTICS,
        config={"score_threshold": 0.3, "nms_threshold": 0.45, "top_k": 300,
                "num_keypoints": 17},
    ),
    dict(
        task="instance_segmentation", task_legacy="instance_segmentation",
        family="yolo_preopt_seg",
        variants=(_preopt("yolo11", _SIZES, "-seg") + _preopt("yolov8", _SIZES, "-seg")
                  + [f"yolov12-seg-{s}_640x640_pre-optimized" for s in _SIZES]
                  + [f"yolov9-seg-{s}_640x640_pre-optimized"
                     for s in ("c", "e", "gelan-c")]),
        preprocessor=LETTERBOX,
        postprocessor=_proc("PreoptSegPostprocessor", WHC),
        visualizer=_proc("InstanceSegVisualizer", []),
        base="IInstanceSegFactory", reference=REF_ULTRALYTICS,
        config={"score_threshold": 0.3, "nms_threshold": 0.45, "top_k": 300,
                "num_mask_coefs": 32},
    ),

    # ============================ plain YOLO (25) ===============================
    dict(
        task="object_detection", task_legacy="object_detection", family="yolov12",
        variants=_plain("yolov12", _SIZES),
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8Postprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_YOLOV12,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="object_detection", task_legacy="object_detection", family="yolov13",
        variants=_plain("yolov13", ("n", "s", "l", "x")),
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8Postprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_YOLOV13,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="object_detection", task_legacy="object_detection", family="yolov9",
        variants=["yolov9-e_640x640"],
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8Postprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_YOLOV9,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="object_detection", task_legacy="object_detection", family="yolov6",
        variants=["yolov6-m6_1280x1280"],
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8Postprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_YOLOV6,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="instance_segmentation", task_legacy="instance_segmentation",
        family="yolov12_seg",
        variants=[f"yolov12-seg-{s}_640x640" for s in _SIZES],
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8InstanceSegPostprocessor", WHC),
        visualizer=_proc("InstanceSegVisualizer", []),
        base="IInstanceSegFactory", reference=REF_YOLOV12,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="instance_segmentation", task_legacy="instance_segmentation",
        family="yolov9_seg",
        variants=[f"yolov9-seg-{s}_640x640" for s in ("c", "e", "gelan-c")],
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8InstanceSegPostprocessor", WHC),
        visualizer=_proc("InstanceSegVisualizer", []),
        base="IInstanceSegFactory", reference=REF_YOLOV9,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="yolov12_cls",
        variants=[f"yolov12-cls-{s}_224x224" for s in _SIZES],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_YOLOV12,
        config={"top_k": 5},
    ),
    dict(
        # Gap fill: dx-modelzoo's yolo11-pose holds n/s/m/x but not l.
        task="pose_estimation", task_legacy="pose_estimation", family="yolo11_pose",
        variants=["yolo11-l-pose_640x640"],
        preprocessor=LETTERBOX,
        postprocessor=_proc("YOLOv8PosePostprocessor", WHC),
        visualizer=_proc("PoseVisualizer", []),
        base="IPoseFactory", reference=REF_ULTRALYTICS,
        config={"score_threshold": 0.4, "nms_threshold": 0.5},
    ),

    # ============================ RT-DETR (20) ==================================
    dict(
        task="object_detection", task_legacy="object_detection", family="rtdetr",
        variants=["rtdetr-hgnetv2-h-6x_640x640", "rtdetr-hgnetv2-l-6x_640x640",
                  "rtdetr-hgnetv2-x-6x_640x640", "rtdetr-r101vd-6x_640x640",
                  "rtdetr-r18vd-6x_640x640", "rtdetr-r34vd-6x_640x640",
                  "rtdetr-r50vd-6x_640x640", "rtdetr-r50vd-m-6x_640x640",
                  "rtdetrv2-r101vd-6x_640x640", "rtdetrv2-r18vd-120e_640x640",
                  "rtdetrv2-r34vd-120e_640x640", "rtdetrv2-r50vd-6x_640x640",
                  "rtdetrv2-r50vd-m-7x_640x640", "rtdetrv3-r18vd-6x_640x640",
                  "rtdetrv3-r50vd-6x_640x640"],
        preprocessor=SIMPLE,
        postprocessor=_proc("RTDETRPostprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_PADDLEDET,
        # NMS-free by construction: nms_threshold 1.0 keeps every query. RT-DETR's own
        # preprocessing is a plain resize, so there is no letterbox to undo.
        config={"score_threshold": 0.4, "nms_threshold": 1.0},
    ),
    dict(
        task="instance_segmentation", task_legacy="instance_segmentation",
        family="mask_rtdetr",
        variants=[f"mask-rtdetr-hgnetv2-{s}-6x_640x640"
                  for s in ("s", "m", "l", "x", "h")],
        preprocessor=SIMPLE,
        postprocessor=_proc("MaskRTDETRPostprocessor", WHC),
        visualizer=_proc("InstanceSegVisualizer", []),
        base="IInstanceSegFactory", reference=REF_PADDLEDET,
        config={"score_threshold": 0.4, "nms_threshold": 1.0},
    ),

    # ============================ classification (17) ===========================
    dict(
        task="image_classification", task_legacy="classification", family="pphgnet",
        variants=[f"pphgnet-{s}_224x224" for s in ("tiny", "small", "base")],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_PADDLECLAS,
        config={"top_k": 5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="pphgnetv2",
        variants=[f"pphgnetv2-b{i}_224x224" for i in range(7)],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_PADDLECLAS,
        config={"top_k": 5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="pplcnetv2",
        variants=[f"pplcnetv2-{s}_224x224" for s in ("small", "base", "large")],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_PADDLECLAS,
        config={"top_k": 5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="swin",
        variants=["swin-b_224x224"],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_SWIN,
        config={"top_k": 5},
    ),
    dict(
        # Joins the existing dx-modelzoo 'vit' family (5 published variants).
        task="image_classification", task_legacy="classification", family="vit",
        variants=["vit-l-p16_512x512_swag", "vit-b-p16_384x384", "vit-t-p16_224x224"],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_VIT,
        config={"top_k": 5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="beit",
        variants=["beit-l-p16_384x384"],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_TORCHVISION,
        config={"top_k": 5},
    ),
    dict(
        task="image_classification", task_legacy="classification", family="levit",
        variants=["levit-128s_224x224"],
        preprocessor=SIMPLE,
        postprocessor=_proc("ClassificationPostprocessor", WHC),
        visualizer=_proc("ClassificationVisualizer", []),
        base="IClassificationFactory", reference=REF_TORCHVISION,
        config={"top_k": 5},
    ),

    # ============================ segmentation (8) ==============================
    dict(
        task="semantic_segmentation", task_legacy="semantic_segmentation",
        family="ddrnet",
        variants=["ddrnet23_1024x2048", "ddrnet23-slim_1024x2048"],
        preprocessor=SIMPLE,
        postprocessor=_proc("SemanticSegmentationPostprocessor", WHC),
        visualizer=_proc("SemanticSegmentationVisualizer", []),
        base="ISegmentationFactory", reference=REF_DDRNET,
        config={"num_classes": 19},
    ),
    dict(
        # Joins the existing dx-modelzoo 'stdc-seg' family (stdc2-seg50_512x1024).
        task="semantic_segmentation", task_legacy="semantic_segmentation",
        family="stdc_seg",
        variants=["stdc1-seg50_512x1024", "stdc1-seg75_768x1536",
                  "stdc2-seg75_768x1536"],
        preprocessor=SIMPLE,
        postprocessor=_proc("SemanticSegmentationPostprocessor", WHC),
        visualizer=_proc("SemanticSegmentationVisualizer", []),
        base="ISegmentationFactory", reference=REF_STDC,
        config={"num_classes": 19},
    ),
    dict(
        task="semantic_segmentation", task_legacy="semantic_segmentation",
        family="pp_liteseg",
        variants=["pp-liteseg-stdc1-camvid-10k_960x720"],
        preprocessor=SIMPLE,
        postprocessor=_proc("SemanticSegmentationPostprocessor", WHC),
        visualizer=_proc("SemanticSegmentationVisualizer", []),
        base="ISegmentationFactory", reference=REF_PADDLESEG,
        config={"num_classes": 11},          # CamVid
    ),
    dict(
        task="semantic_segmentation", task_legacy="semantic_segmentation",
        family="ppmatting",
        variants=["ppmatting-hrnet-w48-composition_512x512",
                  "ppmatting-hrnet-w48-distinctions_512x512"],
        preprocessor=SIMPLE,
        postprocessor=_proc("PPMattingPostprocessor", WHC),
        visualizer=_proc("SemanticSegmentationVisualizer", []),
        base="ISegmentationFactory", reference=REF_PADDLESEG,
        config={"alpha_threshold": 0.5},
    ),

    # ============================ anomaly detection (4) =========================
    dict(
        task="anomaly_detection", task_legacy="anomaly_detection",
        family="efficientad",
        variants=[f"efficientad-m-{p}_256x256"
                  for p in ("teacher", "student", "autoencoder")],
        preprocessor=SIMPLE,
        postprocessor=_proc("AnomalyFeaturePostprocessor", WHC),
        visualizer=_proc("AnomalyVisualizer", []),
        base="IAnomalyDetectionFactory", reference=REF_EFFICIENTAD,
        config={},
    ),
    dict(
        task="anomaly_detection", task_legacy="anomaly_detection", family="patchcore",
        variants=["patchcore_224x224"],
        preprocessor=SIMPLE,
        postprocessor=_proc("AnomalyFeaturePostprocessor", WHC),
        visualizer=_proc("AnomalyVisualizer", []),
        base="IAnomalyDetectionFactory", reference=REF_PATCHCORE,
        config={},
    ),

    # ============================ CLIP / embedding (6) ==========================
    dict(
        task="zero_shot_image_classification", task_legacy="embedding", family="clip",
        variants=["clip-img_resnet50_224x224_openai"],
        preprocessor=CLIP_SIMPLE,
        postprocessor=_proc("CLIPImagePostprocessor", WHC),
        visualizer=_proc("EmbeddingVisualizer", []),
        base="IEmbeddingFactory", reference=REF_CLIP, config={},
    ),
    dict(
        task="zero_shot_image_classification", task_legacy="embedding", family="clip",
        variants=["clip-img_vit-b16-quickgelu_224x224_metaclip-fullcc"],
        preprocessor=CLIP_SIMPLE,
        postprocessor=_proc("CLIPImagePostprocessor", WHC),
        visualizer=_proc("EmbeddingVisualizer", []),
        base="IEmbeddingFactory", reference=REF_METACLIP, config={},
    ),
    dict(
        # Text encoder: the .dxnn takes [1, 77, 512] token embeddings, not an image.
        # See the family README for the open_clip snippet that produces them.
        task="zero_shot_image_classification", task_legacy="embedding", family="clip",
        variants=["clip-text_resnet50_77x512_openai"],
        preprocessor=SIMPLE,
        postprocessor=_proc("CLIPTextPostprocessor", WHC),
        visualizer=_proc("EmbeddingVisualizer", []),
        base="IEmbeddingFactory", reference=REF_CLIP, config={},
    ),
    dict(
        task="super_resolution", task_legacy="embedding", family="pp_shitu_rec",
        variants=["pp-shituv2-feature-extraction_224x224"],
        preprocessor=SIMPLE,
        postprocessor=_proc("GenericEmbeddingPostprocessor", WHC),
        visualizer=_proc("EmbeddingVisualizer", []),
        base="IEmbeddingFactory", reference=REF_PADDLECLAS, config={},
    ),
    dict(
        task="image_classification", task_legacy="reid", family="repvgg_reid",
        variants=["repvgg-a0-reid_256x128"],
        preprocessor=SIMPLE,
        postprocessor=_proc("GenericEmbeddingPostprocessor", WHC),
        visualizer=_proc("EmbeddingVisualizer", []),
        base="IEmbeddingFactory", reference=REF_PADDLECLAS, config={},
    ),

    # ============================ PP-ShiTu detection (2) ========================
    dict(
        # PP-PicoDet mainbody detector, one foreground class. PicoDet and NanoDet-Plus
        # share the GFL/DFL head, and NanoDetPostprocessor auto-detects reg_max and the
        # anchor grid from the tensor shape, so it covers this without a new class.
        task="object_detection", task_legacy="object_detection", family="pp_shitu",
        variants=["pp-shituv1-mainbody-detection_640x640",
                  "pp-shituv2-mainbody-detection_640x640"],
        preprocessor=LETTERBOX,
        postprocessor=_proc("NanoDetPostprocessor", WHC),
        visualizer=_proc("DetectionVisualizer", []),
        base="IDetectionFactory", reference=REF_PADDLECLAS,
        config={"num_classes": 1, "conf_threshold": 0.4, "nms_threshold": 0.5},
    ),

    # ============================ DarkPose (1) ==================================
    dict(
        # VitPosePostprocessor is a shape-agnostic heatmap argmax decoder: it reads
        # (num_keypoints, hm_h, hm_w) off the tensor, so HRNet-W32's [1, 17, 64, 48]
        # decodes without a new class. It uses the standard quarter-offset shift rather
        # than DarkPose's distribution-aware refinement, so keypoints land a fraction of
        # a heatmap cell less precisely than the published DarkPose metric.
        task="pose_estimation", task_legacy="pose_estimation", family="dark_hrnet",
        variants=["dark-hrnet-w32_256x192"],
        preprocessor=SIMPLE,
        postprocessor=_proc("VitPosePostprocessor", WHC),
        visualizer=_proc("PoseVisualizer", []),
        base="IPoseFactory", reference=REF_HRNET,
        config={"num_keypoints": 17},
    ),
]

# Models that ARE downloadable today: the 4 zoo rows carrying a q-master .dxnn but no
# q-lite one. Measured 2026-09-22: HTTP 200 at modelzoo/q-master-dxnn/2_4_0/.
Q_MASTER_ONLY = frozenset({
    "beit-l-p16_384x384", "levit-128s_224x224",
    "vit-b-p16_384x384", "vit-t-p16_224x224",
})


def _legacy_model_name(variant: str) -> str:
    """A unique legacy-compatible key. Variants are unique, so this is too."""
    return variant.replace("-", "_").replace(".", "_")


def expand() -> list[dict]:
    """One fully resolved row per variant, in the shape the emitter consumes."""
    rows: list[dict] = []
    for group in GROUPS:
        for variant in group["variants"]:
            if variant not in ZOO_ROWS:
                raise KeyError(f"{variant} is not in the harvested zoo table")
            display_name, _, zoo_task, dataset, license_ = ZOO_ROWS[variant]
            width, height = resolution(variant)
            rows.append({
                "variant": variant,
                "task": group["task"],
                "task_legacy": group["task_legacy"],
                "family": group["family"],
                "width": width,
                "height": height,
                "display_name": display_name,
                "zoo_task": zoo_task,
                "dataset": dataset,
                "license": license_,
                "reference": group["reference"],
                "config": dict(group["config"]),
                "preprocessor": group["preprocessor"],
                "postprocessor": group["postprocessor"],
                "visualizer": group["visualizer"],
                "factory_bases": [group["base"]],
                "imports": [
                    f"from common.base import {group['base']}",
                    f"from common.processors import {group['preprocessor']['class']}, "
                    f"{group['postprocessor']['class']}",
                    f"from common.visualizers import {group['visualizer']['class']}",
                ],
                "legacy_model_name": _legacy_model_name(variant),
                "manifest_category": MANIFEST_CATEGORY[group["task_legacy"]],
                "published": variant in Q_MASTER_ONLY,
            })
    return rows


def self_check() -> None:
    """Fail loudly on a table that cannot be what it claims to be."""
    rows = expand()
    variants = [r["variant"] for r in rows]
    duplicates = {v for v in variants if variants.count(v) > 1}
    if duplicates:
        raise AssertionError(f"variant declared twice: {sorted(duplicates)}")
    missing = set(ZOO_ROWS) - set(variants)
    if missing:
        raise AssertionError(f"zoo row never claimed by a group: {sorted(missing)}")
    if len(rows) != 147:
        raise AssertionError(f"expected 147 rows, got {len(rows)}")
    # One family must live in exactly one task: CMake target names are family-derived.
    owner: dict[str, str] = {}
    for r in rows:
        if owner.setdefault(r["family"], r["task"]) != r["task"]:
            raise AssertionError(
                f"family {r['family']} spans {owner[r['family']]} and {r['task']}")


if __name__ == "__main__":
    self_check()
    rows = expand()
    print(f"{len(rows)} rows, {len({r['family'] for r in rows})} families, "
          f"{len({r['task'] for r in rows})} tasks, "
          f"{sum(1 for r in rows if r['published'])} published")

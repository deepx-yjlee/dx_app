## feat/per-model-example-dirs (multi-model graph, per-variant layout)
### 1. Changed
- DX-RT 3.5.0 or later is required: `./setup.sh` downloads DX Model Zoo 2_5_0, whose `.dxnn` files are container v9, which DX-RT 3.5.0 is the first runtime to load. NPU driver 2.7.0 or later; `dx_engine` 3.5.x (it refuses a runtime of another major.minor). The C++ examples check DX-RT >= 3.5.0 when they start. Tested with DX-RT 3.5.0 (build 1.6fdc543, from dx_rt f743c41, v3.5.0 rc), NPU driver 2.7.0 (from 8455be6, v2.7.0 rc) and firmware 2.7.4 on a DX-M1 M.2 card
- Each C++ variant's factory lives in its own namespace, `dxapp::v_<variant>`, so same-named factories of two variants no longer collide; after regenerating factories run `python3 scripts/generate_cpp_family_layout.py --variant-scope src/cpp_example`, which `scripts/ci_checks.sh` checks (`guard-variant-scope`)
- `IPanopticDrivingFactory` gains two pure virtual methods, `createPanopticPostprocessor` and `createPanopticVisualizer`; an out-of-tree panoptic factory must implement them
- `ModelConfig` applies the nested `"config"` object of a variant's `config.json` over the top level
- The multi-model graph cuts an ROI crop by `PaddedCropRect` in `common/utility/roi_crop.hpp`
- C++ image classification results are now softmax probabilities, with the ImageNet class name for a 1000-class head, instead of raw logits without a name: this covers every C++ `image_classification` variant whose factory uses `EfficientNetPostprocessor` (134 of them, all but `casvit-m_224x224` and `casvit-t_224x224`). An output that already is a distribution is passed through unchanged; the top-k ranking is the same as before. The Python classification examples already reported softmax probabilities and now also carry the ImageNet class name
### 2. Fixed
- Fixed VitPose and dark-hrnet heatmap decoding (keypoints now match the Python examples within 2.1e-5 px)
- Fixed yolov5-s6-pose decoding and its default thresholds (C++ and Python both use obj 0.25, score 0.3, NMS 0.45)
- Fixed YOLOPv2 async drawing another frame's drivable-area and lane masks; each frame now carries its own masks
- Fixed async runners calling the shared postprocessor from several dxrt callback threads at once; it is now serialized, and `DXAPP_VERIFY` records follow the input order
- Fixed Python async super-resolution ignoring `--loop`
- Fixed an ODR collision between same-named factory classes of different variants linked into one binary
- Fixed the example tests looking up a model's task on the old flat layout; they read it from the task/family/variant tree
- Fixed examples run without `-m` not finding their own model (C++ and Python, [SDKREQ-529](https://deepx.atlassian.net/browse/SDKREQ-529))
- Fixed retrieval/re-id thumbnails and `--check` gallery paths depending on the working directory; both resolve against the repository
### 3. Added
- Multi-model graph engine: a node-graph JSON of registry models wired by frame, ROI and image hand-off edges; CLI `multi_model_graph_sync` / `multi_model_graph_async` (`--check` without the NPU, `--list-models`, `--report`) and the Python module `dx_graph`; sync and async reports are byte-identical
- Shipped sample graphs, including `hand_cascade.json`
- `.dxnn` container check: before loading, the graph names a file this DX-RT cannot load (`.dxnn container v9 needs DX-RT >= 3.5.0 ...`); `--check` and `--list-models` show each file's container version
- Architecture guards (graph boundary, factory uniqueness, model registry, header ODR, C++14, graph models doc, variant scope) in `scripts/ci_checks.sh`, run by the `dxapp-checks` GitHub Actions workflow
### 4. Known issues
- C++ async super-resolution runs each frame's tiles with a blocking `Run`, so it is slow on long videos
- espcn-x2 sync on a video is slow (more than 20 minutes on the test device)
- The C++ DX-RT version check runs after the inference engine is created, so on an older DX-RT the runtime's own error about the `.dxnn` may appear first
- yolov5-s6-pose's `registry_config` lists score threshold 0.25, while both runtimes use 0.3 (Python's default); the variant's `"config"` is empty and neither runtime reads `registry_config`
- One pytest session over `tests/cpp_example` and `tests/python_example` together does not collect; run each suite on its own
- `scripts/add_model.sh` still targets the old flat `<task>/<model>/` layout, and it copies the reference model's C++ factory with its `namespace v_<reference variant>` unchanged, so `python3 scripts/generate_cpp_family_layout.py --variant-scope src/cpp_example --check` refuses the new example. Until `add_model.sh` supports the per-variant layout (a follow-up), rename by hand the factory's namespace to `v_<new variant>` (every character other than a letter or digit becomes `_`) and the `dxapp::v_<...>::` qualifier in the new `_sync.cpp` / `_async.cpp`
## PR 409 NOTHING NEW
## PR 411 NOTHING NEW
## PR 406
### 1. Changed
### 2. Fixed
- Fixed SuperPoint keypoints being drawn at the wrong vertical position in the C++ example
- Fixed SuperPoint tracker settings (nn_thresh, max_pixel_dist, track_max_length) being ignored
### 3. Added
## PR 405
### 1. Changed
- `extract_model_package.sh` now prunes `common/` to the files the extracted model actually depends on instead of copying the whole framework (yolov7: 121→29 C++, 103→54 Python); use `--no-prune` for the previous full copy [SR-698](https://deepx.atlassian.net/browse/SR-698)
### 2. Fixed
### 3. Added

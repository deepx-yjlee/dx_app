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

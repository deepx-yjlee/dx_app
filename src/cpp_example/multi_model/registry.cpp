/**
 * @file registry.cpp
 * @brief Factories used by the four pipeline demos.
 *
 * JSON selects among these variants. An unknown variant fails at startup.
 * ppe_yolo26n.dxnn reuses the yolo26-n detection factory with another file.
 */

#include "multi_model/registry.hpp"
#include "multi_model/npu_stage.hpp"

#include "object_detection/yolo26/yolo26-n_640x640/factory/yolo26-n_640x640_factory.hpp"
#include "instance_segmentation/yolo26_seg/yolo26-n-seg_640x640/factory/yolo26-n-seg_640x640_factory.hpp"
#include "depth_estimation/yolo26_depth/yolo26-depth-n_768x768/factory/yolo26-depth-n_768x768_factory.hpp"
#include "pose_estimation/yolo26_pose/yolo26-n-pose_640x640/factory/yolo26-n-pose_640x640_factory.hpp"
#include "pose_estimation/yolo11_pose/yolo11-n-pose_640x640/factory/yolo11-n-pose_640x640_factory.hpp"
#include "face_detection/scrfd/scrfd-500m_640x640/factory/scrfd-500m_640x640_factory.hpp"
#include "hand_detection/mediapipe_hand_detector/mediapipe-hand-detector_192x192/factory/mediapipe-hand-detector_192x192_factory.hpp"
#include "hand_landmark/mediapipe_hands_lite/mediapipe-hands-lite_224x224/factory/mediapipe-hands-lite_224x224_factory.hpp"
#include "zero_shot_image_classification/clip/clip-img_vit-b32_256x256_datacomp-s34b-b86k/factory/clip-img_vit-b32_256x256_datacomp-s34b-b86k_factory.hpp"

namespace dxapp {
namespace {

struct FactoryEntry {
    const char* task;
    const char* family;
    const char* variant;
    std::unique_ptr<IStage> (*make)(const std::string& stageId, const std::string& modelPath);
};

template <typename Factory, typename Result, bool WithOrt>
std::unique_ptr<IStage> makeStage(const std::string& stageId, const std::string& modelPath) {
    return std::unique_ptr<IStage>(
        std::make_unique<NpuStage<Factory, Result, WithOrt>>(stageId, modelPath));
}

const FactoryEntry kEntries[] = {
    {"object_detection", "yolo26", "yolo26-n_640x640",
     &makeStage<Yolo26Factory, DetectionResult, true>},
    {"instance_segmentation", "yolo26_seg", "yolo26-n-seg_640x640",
     &makeStage<Yolo26SegFactory, InstanceSegmentationResult, true>},
    {"depth_estimation", "yolo26_depth", "yolo26-depth-n_768x768",
     &makeStage<Yolo26DepthFactory, DepthResult, false>},
    {"pose_estimation", "yolo26_pose", "yolo26-n-pose_640x640",
     &makeStage<Yolo26PoseFactory, PoseResult, true>},
    {"pose_estimation", "yolo11_pose", "yolo11-n-pose_640x640",
     &makeStage<Yolo11PoseFactory, PoseResult, true>},
    {"face_detection", "scrfd", "scrfd-500m_640x640",
     &makeStage<ScrfdFactory, FaceDetectionResult, true>},
    {"hand_detection", "mediapipe_hand_detector", "mediapipe-hand-detector_192x192",
     &makeStage<MediapipeHandDetectorFactory, FaceDetectionResult, true>},
    {"hand_landmark", "mediapipe_hands_lite", "mediapipe-hands-lite_224x224",
     &makeStage<MediapipeHandsLiteFactory, HandLandmarkResult, false>},
    {"zero_shot_image_classification", "clip", "clip-img_vit-b32_256x256_datacomp-s34b-b86k",
     &makeStage<ClipFactory, EmbeddingResult, false>},
};

}  // namespace

std::unique_ptr<IStage> createRegisteredStage(
    const std::string& task,
    const std::string& family,
    const std::string& variant,
    const std::string& stageId,
    const std::string& modelPath) {
    const std::size_t entryCount = sizeof(kEntries) / sizeof(kEntries[0]);
    for (std::size_t i = 0; i < entryCount; ++i) {
        if (variant != kEntries[i].variant) {
            continue;
        }
        if (task != kEntries[i].task || family != kEntries[i].family) {
            throw PipelineError(
                "stage '" + stageId + "' variant '" + variant +
                "' is registered as " + kEntries[i].task + "/" + kEntries[i].family);
        }
        return kEntries[i].make(stageId, modelPath);
    }
    throw PipelineError(
        "stage '" + stageId + "' variant '" + variant +
        "' is not registered in the C++ multi-model runner");
}

}  // namespace dxapp

/**
 * @file yolo_preopt_pose_factory.hpp
 * @brief YOLO-pose-preopt factory -- pre-optimized models, whose head runs inside the .dxnn
 *
 * Hand-written rather than carried over from a donor: no other family in this tree
 * consumes a pre-optimized model, so there is no existing factory whose behaviour
 * would be right. The postprocessing contract it targets was measured on an M1
 * (DXRT v3.4.2) against dx_yolo26's three real pre-optimized models -- see
 * common/processors/preopt_topk_postprocessor.hpp.
 */

#ifndef YOLO_PREOPT_POSE_FACTORY_HPP
#define YOLO_PREOPT_POSE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/preopt_topk_postprocessor.hpp"
#include "common/visualizers/pose_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>
#include <vector>

namespace dxapp {

class YoloPreoptPoseFactory : public IPoseFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    YoloPreoptPoseFactory(float score_threshold = 0.3f,
                          float nms_threshold = 0.45f)
        : score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<PoseResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // A pre-optimized model carries a CPU task that DXRT runs through ONNX
        // Runtime; with ORT the postprocessor receives the ready-made top-k table and
        // without it the raw per-stride tensors. The decoder handles both, so the flag
        // changes nothing here.
        (void)is_ort_configured;
        return std::make_unique<PreoptPosePostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            top_k_, num_keypoints_);
    }

    VisualizerPtr<PoseResult> createVisualizer() override {
        return std::make_unique<PoseVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
        top_k_ = config.get<int>("top_k", top_k_);
        num_keypoints_ = config.get<int>("num_keypoints", num_keypoints_);
    }

    std::string getModelName() const override { return "YOLO-pose-preopt"; }
    std::string getTaskType() const override { return "pose_estimation"; }

private:
    std::string variant_;
    float score_threshold_;
    float nms_threshold_;
    // The model itself selects this many rows; the decoder never needs more.
    int top_k_{300};
    int num_keypoints_{17};
};

}  // namespace dxapp

#endif  // YOLO_PREOPT_POSE_FACTORY_HPP

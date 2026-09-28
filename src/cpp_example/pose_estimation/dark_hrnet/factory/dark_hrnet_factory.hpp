/**
 * @file dark_hrnet_factory.hpp
 * @brief DarkHrnet Abstract Factory implementation
 */

#ifndef DARK_HRNET_FACTORY_HPP
#define DARK_HRNET_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/pose_postprocessor.hpp"
#include "common/visualizers/pose_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

// Carried over from pose_estimation/vitpose: this family was added
// after the restructure, so it has no original factory of its own,
// and that family's postprocessing is what dark_hrnet needs. Only the
// class name, include guard and identity differ.

namespace dxapp {

class DarkHrnetFactory : public IPoseFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    DarkHrnetFactory(float score_threshold = 0.25f, float nms_threshold = 0.65f)
        : score_threshold_(score_threshold), nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<PoseResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        return std::make_unique<YOLOv8PosePostprocessor>(
            input_width, input_height, score_threshold_, nms_threshold_,
            is_ort_configured);
    }

    VisualizerPtr<PoseResult> createVisualizer() override {
        return std::make_unique<PoseVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "DarkHrnet" : variant_;
    }
    std::string getTaskType() const override { return "pose_estimation"; }

private:
    std::string variant_;
    float score_threshold_;
    float nms_threshold_;
};

}  // namespace dxapp

#endif  // DARK_HRNET_FACTORY_HPP

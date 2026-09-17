/**
 * @file sfa3d_factory.hpp
 * @brief SFA3D 608x608 factory
 */

#ifndef SFA3D_FACTORY_HPP
#define SFA3D_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/sfa3d_bev_preprocessor.hpp"
#include "common/processors/sfa3d_postprocessor.hpp"
#include "common/visualizers/sfa3d_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Sfa3dFactory : public I3DDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    explicit Sfa3dFactory(
        float score_threshold = 0.3f,
        float nms_threshold = 0.2f)
        : score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SFA3DBEVPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<Detection3DResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        (void)is_ort_configured;
        return std::make_unique<SFA3DPostprocessor>(
            input_width, input_height, score_threshold_, nms_threshold_);
    }

    VisualizerPtr<Detection3DResult> createVisualizer() override {
        return std::make_unique<SFA3DVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override { return "sfa3d_608x608"; }
    std::string getTaskType() const override { return "3d_detection"; }

private:
    std::string variant_;
    float score_threshold_;
    float nms_threshold_;
};

}  // namespace dxapp

#endif  // SFA3D_FACTORY_HPP

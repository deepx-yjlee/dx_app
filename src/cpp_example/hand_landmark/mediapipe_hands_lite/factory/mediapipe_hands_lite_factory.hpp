/**
 * @file mediapipe_hands_lite_factory.hpp
 * @brief Hand Landmark Lite Abstract Factory implementation for hand landmark
 */

#ifndef MEDIAPIPE_HANDS_LITE_FACTORY_HPP
#define MEDIAPIPE_HANDS_LITE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/config/model_config.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/hand_landmark_postprocessor.hpp"
#include "common/visualizers/hand_landmark_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class MediapipeHandsLiteFactory : public IHandLandmarkFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    MediapipeHandsLiteFactory(float confidence_threshold = 0.5f)
        : confidence_threshold_(confidence_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<HandLandmarkResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<HandLandmarkPostprocessor>(
            input_width, input_height, confidence_threshold_);
    }

    VisualizerPtr<HandLandmarkResult> createVisualizer() override {
        return std::make_unique<HandLandmarkVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        confidence_threshold_ = config.get<float>("confidence_threshold", confidence_threshold_);
    }

    std::string getModelName() const override { return "Handlandmarklite_1"; }
    std::string getTaskType() const override { return "hand_landmark"; }

private:
    std::string variant_;
    float confidence_threshold_;
};

}  // namespace dxapp

#endif  // MEDIAPIPE_HANDS_LITE_FACTORY_HPP

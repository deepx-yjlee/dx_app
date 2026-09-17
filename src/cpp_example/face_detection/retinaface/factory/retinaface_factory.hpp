/**
 * @file retinaface_factory.hpp
 * @brief RetinaFace MobileNet0.25 Abstract Factory for face detection
 *
 * Anchor-based face detection with 5-point landmarks.
 */

#ifndef RETINAFACE_FACTORY_HPP
#define RETINAFACE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/retinaface_postprocessor.hpp"
#include "common/visualizers/face_visualizer.hpp"
#include "common/config/model_config.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/simple_resize_preprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class RetinafaceFactory : public IFaceDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    RetinafaceFactory(float score_threshold = 0.5f,
                      float nms_threshold = 0.4f)
        : score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "retinaface_mobilenetv1_736x1280") {
        // BGR float32 with per-channel mean subtraction [104, 117, 123]
        // color_conversion=-1: keep BGR (no RGB conversion)
        return std::make_unique<SimpleResizePreprocessor>(
            input_width, input_height,
            -1,    // keep BGR, no color conversion
            false, // no store_source
            std::array<float, 3>{104.f, 117.f, 123.f},
            true   // output float32
        );
            }
        // default: retinaface_mobilenet-0.25_640x640
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<FaceDetectionResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "retinaface_mobilenetv1_736x1280") {
        (void)is_ort_configured;
        return std::make_unique<RetinaFacePostprocessor>(
            input_width, input_height, score_threshold_, nms_threshold_);
            }
        // default: retinaface_mobilenet-0.25_640x640
        (void)is_ort_configured;
        return std::make_unique<RetinaFacePostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_
        );
    }

    VisualizerPtr<FaceDetectionResult> createVisualizer() override {
        return std::make_unique<FaceVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override { return "RetinaFace-MobileNet0.25"; }
    std::string getTaskType() const override { return "face_detection"; }

private:
    std::string variant_;
    float score_threshold_;
    float nms_threshold_;
};

}  // namespace dxapp

#endif  // RETINAFACE_FACTORY_HPP

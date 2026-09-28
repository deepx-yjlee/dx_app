/**
 * @file yolo26_obb_factory.hpp
 * @brief Yolo26l_obb Abstract Factory implementation
 * 
 * Creates matching components for YOLOv26 OBB (Oriented Bounding Box) detection.
 */

#ifndef YOLO26_OBB_FACTORY_HPP
#define YOLO26_OBB_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/obb_postprocessor.hpp"
#include "common/visualizers/obb_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Yolo26ObbFactory : public IOBBFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    explicit Yolo26ObbFactory(float score_threshold = 0.3f)
        : score_threshold_(score_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<OBBResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        return std::make_unique<YOLOv26OBBPostprocessor>(
            input_width, input_height,
            score_threshold_,
            is_ort_configured
        );
    }

    VisualizerPtr<OBBResult> createVisualizer() override {
        return std::make_unique<OBBVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "Yolo26l_obb" : variant_;
    }
    std::string getTaskType() const override { return "obb_detection"; }

private:
    std::string variant_;
    float score_threshold_;
};

}  // namespace dxapp

#endif  // YOLO26_OBB_FACTORY_HPP

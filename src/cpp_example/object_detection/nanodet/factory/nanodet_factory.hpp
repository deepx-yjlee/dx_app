/**
 * @file nanodet_factory.hpp
 * @brief NanoDetplusm_15 Abstract Factory implementation
 * 
 * Uses v3-native NanoDet postprocessor with DFL decoding.
 */

#ifndef NANODET_FACTORY_HPP
#define NANODET_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/nanodet_postprocessor.hpp"
#include "common/visualizers/detection_visualizer.hpp"
#include "common/config/model_config.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/yolo_detection_postprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class NanodetFactory : public IDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    NanodetFactory(float score_threshold = 0.35f,
                   float nms_threshold = 0.6f,
                   int reg_max = 7)
        : score_threshold_(score_threshold),
          nms_threshold_(nms_threshold),
          reg_max_(reg_max) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<DetectionResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "nanodet-repvgg-a12_224x224") {
        return std::make_unique<YOLOXPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            num_classes_,
            class_names_
        );
            }
        // default: nanodet-plus-1.5x_224x224
        (void)is_ort_configured;
        return std::make_unique<NanoDetPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_, num_classes_, reg_max_,
            false, class_names_
        );
    }

    VisualizerPtr<DetectionResult> createVisualizer() override {
        return std::make_unique<DetectionVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
        num_classes_ = config.get<int>("num_classes", num_classes_);
        class_names_ = config.get_string_list("class_names");
        reg_max_ = config.get<int>("reg_max", reg_max_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "NanoDetplusm_15" : variant_;
    }
    std::string getTaskType() const override { return "object_detection"; }

private:
    std::string variant_;
    float obj_threshold_;  // from a sibling variant in this family
    float score_threshold_;
    float nms_threshold_;
    int num_classes_{80};
    int reg_max_;
    std::vector<std::string> class_names_;
};

}  // namespace dxapp

#endif  // NANODET_FACTORY_HPP

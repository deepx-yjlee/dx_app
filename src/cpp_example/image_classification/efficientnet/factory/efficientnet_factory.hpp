/**
 * @file efficientnet_factory.hpp
 * @brief EfficientNetb2 Abstract Factory implementation for classification
 */

#ifndef EFFICIENTNET_FACTORY_HPP
#define EFFICIENTNET_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/classification_postprocessor.hpp"
#include "common/visualizers/classification_visualizer.hpp"
#include "common/config/model_config.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/simple_resize_preprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class EfficientnetFactory : public IClassificationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    EfficientnetFactory(int num_classes = 1000, int top_k = 5)
        : num_classes_(num_classes), top_k_(top_k) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "efficientnet-b7_600x600") {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
            }
        if (variant_ == "efficientnetv2-m_480x480") {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
            }
        // default: efficientnet-b2_288x288
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<ClassificationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<EfficientNetPostprocessor>(num_classes_, top_k_);
    }

    VisualizerPtr<ClassificationResult> createVisualizer() override {
        return std::make_unique<ClassificationResultVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        num_classes_ = config.get<int>("num_classes", num_classes_);
        top_k_ = config.get<int>("top_k", top_k_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "EfficientNetb2" : variant_;
    }
    std::string getTaskType() const override { return "classification"; }

private:
    std::string variant_;
    int num_classes_;
    int top_k_;
};

}  // namespace dxapp

#endif  // EFFICIENTNET_FACTORY_HPP

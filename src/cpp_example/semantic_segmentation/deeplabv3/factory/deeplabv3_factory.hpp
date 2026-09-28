/**
 * @file deeplabv3_factory.hpp
 * @brief Deeplabv3Factory Abstract Factory implementation
 */

#ifndef DEEPLABV3_FACTORY_HPP
#define DEEPLABV3_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"
#include "common/config/model_config.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/letterbox_preprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Deeplabv3Factory : public ISegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Deeplabv3Factory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "deeplabv3_mobilenetv2_512x512") {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
            }
        if (variant_ == "deeplabv3plus_mobilenetv1_512x512") {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
            }
        if (variant_ == "deeplabv3plus_mobilenetv2_512x512") {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
            }
        // default: deeplabv3-resnet101_512x512
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<SegmentationResult> createPostprocessor(
        int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "deeplabv3_mobilenetv2_512x512") {
        return std::make_unique<DeepLabv3Postprocessor>(
            input_width, input_height
        );
            }
        if (variant_ == "deeplabv3plus_mobilenetv1_512x512") {
        return std::make_unique<DeepLabv3Postprocessor>(
            input_width, input_height
        );
            }
        if (variant_ == "deeplabv3plus_mobilenetv2_512x512") {
        return std::make_unique<DeepLabv3Postprocessor>(
            input_width, input_height
        );
            }
        // default: deeplabv3-resnet101_512x512
        return std::make_unique<DeepLabv3Postprocessor>(input_width, input_height);
    }

    VisualizerPtr<SegmentationResult> createVisualizer() override {
        return std::make_unique<SemanticSegmentationVisualizer>();
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "Deeplabv3 Resnet101" : variant_;
    }
    std::string getTaskType() const override { return "semantic_segmentation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // DEEPLABV3_FACTORY_HPP

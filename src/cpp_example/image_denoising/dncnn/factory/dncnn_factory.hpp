/**
 * @file dncnn_factory.hpp
 * @brief DnCNN_15 Abstract Factory implementation for image restoration
 * 
 * Uses v3-native DnCNN postprocessor with grayscale preprocessor.
 */

#ifndef DNCNN_FACTORY_HPP
#define DNCNN_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/grayscale_preprocessor.hpp"
#include "common/processors/restoration_postprocessor.hpp"
#include "common/visualizers/restoration_visualizer.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/simple_resize_preprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class DncnnFactory : public IRestorationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    DncnnFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "dncnn-color_512x512") {
        // Color model (3-channel) — use simple resize, not grayscale
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
            }
        // default: dncnn-15_512x512
        return std::make_unique<GrayscaleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<RestorationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<DnCNNPostprocessor>(
            input_width, input_height
        );
    }

    VisualizerPtr<RestorationResult> createVisualizer() override {
        return std::make_unique<RestorationVisualizer>();
    }

    std::string getModelName() const override { return "DnCNN_15"; }
    std::string getTaskType() const override { return "image_denoising"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // DNCNN_FACTORY_HPP

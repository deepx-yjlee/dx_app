/**
 * @file zerodce_factory.hpp
 * @brief ZerodceFactory Abstract Factory implementation for ZeroDCE++ image enhancement
 *
 * ZeroDCE++ outputs 4 iterations × 3 channels = 12-channel curve parameter maps.
 * The runner auto-detects the number of iterations from the output tensor.
 */

#ifndef ZERODCE_FACTORY_HPP
#define ZERODCE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/zero_dce_postprocessor.hpp"
#include "common/visualizers/restoration_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class ZerodceFactory : public IRestorationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    ZerodceFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "zerodce_400x600") {
        // store_source=true: store resized RGB for LE curve in postprocessor
        return std::make_unique<SimpleResizePreprocessor>(
            input_width, input_height, cv::COLOR_BGR2RGB, true);
            }
        // default: zerodce-pp_400x600
        return std::make_unique<SimpleResizePreprocessor>(
            input_width, input_height, cv::COLOR_BGR2RGB, true);
    }

    PostprocessorPtr<RestorationResult> createPostprocessor(
        int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "zerodce_400x600") {
        return std::make_unique<ZeroDCEPostprocessor>(
            input_width, input_height, 8  // 8 iterations
        );
            }
        // default: zerodce-pp_400x600
        return std::make_unique<ZeroDCEPostprocessor>(
            input_width, input_height, 4  // ZeroDCE++ uses 4 iterations
        );
    }

    VisualizerPtr<RestorationResult> createVisualizer() override {
        return std::make_unique<RestorationVisualizer>();
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "Zero-DCE++" : variant_;
    }
    std::string getTaskType() const override { return "image_enhancement"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // ZERODCE_FACTORY_HPP

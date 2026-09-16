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
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit ZerodceFactory(std::string variant) : variant_(std::move(variant)) {}

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

    std::string getModelName() const override { return "Zero-DCE++"; }
    std::string getTaskType() const override { return "image_enhancement"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // ZERODCE_FACTORY_HPP

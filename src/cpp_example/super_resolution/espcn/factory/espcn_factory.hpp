/**
 * @file espcn_factory.hpp
 * @brief EspcnFactory Abstract Factory implementation
 */

#ifndef ESPCN_FACTORY_HPP
#define ESPCN_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/espcn_postprocessor.hpp"
#include "common/visualizers/restoration_visualizer.hpp"
#include "common/config/model_config.hpp"

// Includes required by bodies spliced in from sibling variants.
#include "common/processors/grayscale_preprocessor.hpp"

#include <string>
#include <utility>

namespace dxapp {

class EspcnFactory : public IRestorationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    EspcnFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "espcn-x3_17x17") {
        // store_source=true: store BGR image for CbCr extraction in postprocessor
        return std::make_unique<GrayscaleResizePreprocessor>(input_width, input_height, true);
            }
        if (variant_ == "espcn-x4_17x17") {
        // store_source=true: store BGR image for CbCr extraction in postprocessor
        return std::make_unique<GrayscaleResizePreprocessor>(input_width, input_height, true);
            }
        // default: espcn-x2_17x17
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<RestorationResult> createPostprocessor(
        int input_width, int input_height) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "espcn-x3_17x17") {
        return std::make_unique<ESPCNPostprocessor>(
            input_width, input_height, 4  // scale_factor=4
        );
            }
        if (variant_ == "espcn-x4_17x17") {
        return std::make_unique<ESPCNPostprocessor>(
            input_width, input_height, 4  // scale_factor=4
        );
            }
        // default: espcn-x2_17x17
        return std::make_unique<ESPCNPostprocessor>(input_width, input_height);
    }

    VisualizerPtr<RestorationResult> createVisualizer() override {
        return std::make_unique<RestorationVisualizer>();
    }

    std::string getModelName() const override { return "Espcn X2"; }
    std::string getTaskType() const override { return "super_resolution"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // ESPCN_FACTORY_HPP

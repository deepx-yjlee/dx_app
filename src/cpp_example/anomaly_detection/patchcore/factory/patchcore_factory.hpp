/**
 * @file patchcore_factory.hpp
 * @brief PatchCore factory
 *
 * Hand-written, not carried over from a donor: no existing family in this tree
 * consumes this model's output, so there is no factory whose behaviour would be right.
 * The result is a DepthResult and this uses the depth runner and
 * DepthVisualizer: both are continuous per-pixel maps rendered as a
 * colormap, so reusing them avoids a new runner and result type for four
 * models whose .dxnn files do not exist yet. It is a FEATURE RESPONSE,
 * not the published anomaly score -- see the postprocessor header.
 */

#ifndef PATCHCORE_FACTORY_HPP
#define PATCHCORE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/anomaly_postprocessor.hpp"
#include "common/visualizers/depth_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>
#include <vector>

namespace dxapp {

class PatchcoreFactory : public IDepthEstimationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    PatchcoreFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<DepthResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<AnomalyFeaturePostprocessor>(
            input_width, input_height);
    }

    VisualizerPtr<DepthResult> createVisualizer() override {
        return std::make_unique<DepthVisualizer>();
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "PatchCore" : variant_;
    }
    std::string getTaskType() const override { return "anomaly_detection"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // PATCHCORE_FACTORY_HPP

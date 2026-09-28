/**
 * @file ppmatting_factory.hpp
 * @brief PP-Matting factory
 *
 * Hand-written, not carried over from a donor: no existing family in this tree
 * consumes this model's output, so there is no factory whose behaviour would be right.
 * A matting model emits a continuous alpha, so the result carries both
 * the thresholded class map (which the visualizer renders) and the matte.
 */

#ifndef PPMATTING_FACTORY_HPP
#define PPMATTING_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/matting_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>
#include <vector>

namespace dxapp {

class PpmattingFactory : public ISegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    PpmattingFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    // ISegmentationFactory's createPostprocessor takes no is_ort_configured flag,
    // unlike the detection and instance-segmentation interfaces.
    PostprocessorPtr<SegmentationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<PPMattingPostprocessor>(
            input_width, input_height, alpha_threshold_);
    }

    VisualizerPtr<SegmentationResult> createVisualizer() override {
        return std::make_unique<SemanticSegmentationVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        alpha_threshold_ = config.get<float>("alpha_threshold", alpha_threshold_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "PP-Matting" : variant_;
    }
    std::string getTaskType() const override { return "semantic_segmentation"; }

private:
    std::string variant_;
    float alpha_threshold_{0.5f};
};

}  // namespace dxapp

#endif  // PPMATTING_FACTORY_HPP

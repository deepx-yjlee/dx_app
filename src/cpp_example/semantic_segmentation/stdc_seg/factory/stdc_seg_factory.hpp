/**
 * @file stdc_seg_factory.hpp
 * @brief StdcSegFactory Abstract Factory implementation
 */

#ifndef STDC_SEG_FACTORY_HPP
#define STDC_SEG_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class StdcSegFactory : public ISegmentationFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit StdcSegFactory(std::string variant) : variant_(std::move(variant)) {}

    StdcSegFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<SegmentationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<DeepLabv3Postprocessor>(input_width, input_height);
    }

    VisualizerPtr<SegmentationResult> createVisualizer() override {
        return std::make_unique<SemanticSegmentationVisualizer>();
    }

    std::string getModelName() const override { return "Stdc2 Seg50"; }
    std::string getTaskType() const override { return "semantic_segmentation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // STDC_SEG_FACTORY_HPP

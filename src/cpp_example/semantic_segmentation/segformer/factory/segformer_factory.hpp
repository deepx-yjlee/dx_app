/**
 * @file segformer_factory.hpp
 * @brief SegFormer-B0 Abstract Factory for semantic segmentation
 *
 * SegFormer outputs argmax-style segmentation maps, reuses DeepLabv3Postprocessor.
 */

#ifndef SEGFORMER_FACTORY_HPP
#define SEGFORMER_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class SegformerFactory : public ISegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    SegformerFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<SegmentationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<DeepLabv3Postprocessor>(
            input_width, input_height, true  // upsample_to_input for smooth boundaries
        );
    }

    VisualizerPtr<SegmentationResult> createVisualizer() override {
        return std::make_unique<SemanticSegmentationVisualizer>();
    }

    std::string getModelName() const override { return "SegFormer-B0"; }
    std::string getTaskType() const override { return "semantic_segmentation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // SEGFORMER_FACTORY_HPP

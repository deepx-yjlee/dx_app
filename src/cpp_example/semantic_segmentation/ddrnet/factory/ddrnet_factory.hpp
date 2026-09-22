/**
 * @file ddrnet_factory.hpp
 * @brief Ddrnet Abstract Factory implementation for semantic segmentation
 * 
 * Uses unified DeepLabv3Postprocessor (NCHW/NHWC, int16/float argmax).
 */

#ifndef DDRNET_FACTORY_HPP
#define DDRNET_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"

#include <string>
#include <utility>

// Carried over from semantic_segmentation/bisenet: this family was added
// after the restructure, so it has no original factory of its own,
// and that family's postprocessing is what ddrnet needs. Only the
// class name, include guard and identity differ.

namespace dxapp {

class DdrnetFactory : public ISegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    DdrnetFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<SegmentationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<DeepLabv3Postprocessor>(
            input_width, input_height
        );
    }

    VisualizerPtr<SegmentationResult> createVisualizer() override {
        return std::make_unique<SemanticSegmentationVisualizer>();
    }

    std::string getModelName() const override { return "Ddrnet"; }
    std::string getTaskType() const override { return "semantic_segmentation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // DDRNET_FACTORY_HPP

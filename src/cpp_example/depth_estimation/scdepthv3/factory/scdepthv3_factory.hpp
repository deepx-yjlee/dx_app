/**
 * @file scdepthv3_factory.hpp
 * @brief Scdepthv3 Abstract Factory implementation for depth estimation
 * 
 * Uses v3-native depth estimation postprocessor.
 */

#ifndef SCDEPTHV3_FACTORY_HPP
#define SCDEPTHV3_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/depth_postprocessor.hpp"
#include "common/visualizers/depth_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Scdepthv3Factory : public IDepthEstimationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Scdepthv3Factory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<DepthResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<FastDepthPostprocessor>(
            input_width, input_height
        );
    }

    VisualizerPtr<DepthResult> createVisualizer() override {
        return std::make_unique<DepthVisualizer>();
    }

    std::string getModelName() const override { return "Scdepthv3"; }
    std::string getTaskType() const override { return "depth_estimation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // SCDEPTHV3_FACTORY_HPP

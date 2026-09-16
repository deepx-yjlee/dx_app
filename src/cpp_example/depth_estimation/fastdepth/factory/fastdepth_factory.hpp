/**
 * @file fastdepth_factory.hpp
 * @brief FastDepth_1 Abstract Factory implementation for depth estimation
 * 
 * Uses v3-native depth estimation postprocessor.
 */

#ifndef FASTDEPTH_FACTORY_HPP
#define FASTDEPTH_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/depth_postprocessor.hpp"
#include "common/visualizers/depth_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class FastdepthFactory : public IDepthEstimationFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit FastdepthFactory(std::string variant) : variant_(std::move(variant)) {}

    FastdepthFactory() = default;

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

    std::string getModelName() const override { return "FastDepth_1"; }
    std::string getTaskType() const override { return "depth_estimation"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // FASTDEPTH_FACTORY_HPP

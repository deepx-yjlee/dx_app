/**
 * @file yolo26_depth_factory.hpp
 * @brief Yolo26DepthFactory Abstract Factory implementation
 *
 * YOLO26-Depth-L monocular depth estimation. The compiled model
 * `yolo26-depth-l_768x768.dxnn` takes a uint8 NHWC input
 * `images` [1,768,768,3] and produces a dense float32 depth map
 * `depth` [1,1,768,768].
 */

#ifndef YOLO26_DEPTH_FACTORY_HPP
#define YOLO26_DEPTH_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/depth_postprocessor.hpp"
#include "common/visualizers/depth_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Yolo26DepthFactory : public IDepthEstimationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Yolo26DepthFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<DepthResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<FastDepthPostprocessor>(input_width, input_height);
    }

    VisualizerPtr<DepthResult> createVisualizer() override {
        return std::make_unique<DepthVisualizer>();
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "YOLO26-Depth-L" : variant_;
    }
    std::string getTaskType() const override { return "depth_estimation"; }

    // getInputNormalization() is intentionally NOT overridden. The compiled model
    // consumes uint8 NHWC directly (the /255 normalization is folded in at
    // compile time), so the default {apply_mean_std = false} keeps the runner
    // on the raw-uint8 path. Declaring a float spec here would hand the engine
    // a 4x-oversized float32 buffer -> out-of-bounds read / segfault.

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // YOLO26_DEPTH_FACTORY_HPP

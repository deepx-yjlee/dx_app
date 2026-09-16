/**
 * @file realesrgan_factory.hpp
 * @brief RealesrganFactory Abstract Factory implementation
 */

#ifndef REALESRGAN_FACTORY_HPP
#define REALESRGAN_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/restoration_postprocessor.hpp"
#include "common/visualizers/restoration_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class RealesrganFactory : public IRestorationFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit RealesrganFactory(std::string variant) : variant_(std::move(variant)) {}

    RealesrganFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<RestorationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<DnCNNPostprocessor>(input_width, input_height);
    }

    VisualizerPtr<RestorationResult> createVisualizer() override {
        return std::make_unique<RestorationVisualizer>();
    }

    std::string getModelName() const override { return "Realesrgan X2"; }
    std::string getTaskType() const override { return "super_resolution"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // REALESRGAN_FACTORY_HPP

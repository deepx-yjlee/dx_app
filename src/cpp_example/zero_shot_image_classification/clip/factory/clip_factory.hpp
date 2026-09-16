/**
 * @file clip_factory.hpp
 * @brief ClipFactory Abstract Factory implementation
 */

#ifndef CLIP_FACTORY_HPP
#define CLIP_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/embedding_postprocessor.hpp"
#include "common/visualizers/embedding_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class ClipFactory : public IEmbeddingFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit ClipFactory(std::string variant) : variant_(std::move(variant)) {}

    ClipFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<EmbeddingResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<GenericEmbeddingPostprocessor>(input_width, input_height);
    }

    VisualizerPtr<EmbeddingResult> createVisualizer() override {
        return std::make_unique<EmbeddingVisualizer>();
    }

    std::string getModelName() const override { return "Clip Rn50X16"; }
    std::string getTaskType() const override { return "embedding"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // CLIP_FACTORY_HPP

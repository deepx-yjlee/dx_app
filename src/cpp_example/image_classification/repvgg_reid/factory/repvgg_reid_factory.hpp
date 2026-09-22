/**
 * @file repvgg_reid_factory.hpp
 * @brief RepvggReid MobileFaceNet Abstract Factory implementation for embedding
 * 
 * Uses v3-native embedding postprocessor with simple resize preprocessor.
 */

#ifndef REPVGG_REID_FACTORY_HPP
#define REPVGG_REID_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/embedding_postprocessor.hpp"
#include "common/visualizers/embedding_visualizer.hpp"

#include <string>
#include <utility>

// Carried over from image_classification/casvit: this family was added
// after the restructure, so it has no original factory of its own,
// and that family's postprocessing is what repvgg_reid needs. Only the
// class name, include guard and identity differ.

namespace dxapp {

class RepvggReidFactory : public IEmbeddingFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    RepvggReidFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<EmbeddingResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<GenericEmbeddingPostprocessor>(
            input_width, input_height, true /* L2 normalize */
        );
    }

    VisualizerPtr<EmbeddingResult> createVisualizer() override {
        return std::make_unique<EmbeddingVisualizer>();
    }

    std::string getModelName() const override { return "RepvggReid"; }
    std::string getTaskType() const override { return "image_classification"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // REPVGG_REID_FACTORY_HPP

/**
 * @file pp_shitu_rec_factory.hpp
 * @brief PpShituRec Abstract Factory implementation
 */

#ifndef PP_SHITU_REC_FACTORY_HPP
#define PP_SHITU_REC_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/embedding_postprocessor.hpp"
#include "common/visualizers/embedding_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

// Carried over from super_resolution/eigenplaces: this family was added
// after the restructure, so it has no original factory of its own,
// and that family's postprocessing is what pp_shitu_rec needs. Only the
// class name, include guard and identity differ.

namespace dxapp {

class PpShituRecFactory : public IEmbeddingFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    PpShituRecFactory() = default;

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

    std::string getModelName() const override { return "PpShituRec"; }
    std::string getTaskType() const override { return "super_resolution"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // PP_SHITU_REC_FACTORY_HPP

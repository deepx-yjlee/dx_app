/**
 * @file 3ddfa_v2_factory.hpp
 * @brief 3DDFA v2 MobileNet 0.5 Abstract Factory for face alignment
 *
 * Uses TDDFA postprocessor with simple resize preprocessor.
 */

#ifndef N3DDFA_V2_FACTORY_HPP
#define N3DDFA_V2_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/tddfa_postprocessor.hpp"
#include "common/visualizers/face_alignment_visualizer.hpp"

#include <string>
#include <utility>

namespace dxapp {

class N3ddfaV2Factory : public IFaceAlignmentFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit N3ddfaV2Factory(std::string variant) : variant_(std::move(variant)) {}

    N3ddfaV2Factory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<FaceAlignmentResult> createPostprocessor(
        int input_width, int input_height, bool /*is_ort_configured*/ = false) override {
        return std::make_unique<TDDFAPostprocessor>(input_width, input_height);
    }

    VisualizerPtr<FaceAlignmentResult> createVisualizer() override {
        return std::make_unique<FaceAlignmentVisualizer>();
    }

    std::string getModelName() const override { return "3ddfa_v2_mobilnet0_5_120x120"; }
    std::string getTaskType() const override { return "face_alignment"; }

private:
    std::string variant_;
};

}  // namespace dxapp

#endif  // N3DDFA_V2_FACTORY_HPP

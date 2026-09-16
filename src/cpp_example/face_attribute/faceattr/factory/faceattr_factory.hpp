/**
 * @file faceattr_factory.hpp
 * @brief Face Attribute ResNet18 Abstract Factory for attribute recognition
 */

#ifndef FACEATTR_FACTORY_HPP
#define FACEATTR_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/attribute_postprocessor.hpp"
#include "common/visualizers/attribute_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class FaceattrFactory : public IClassificationFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit FaceattrFactory(std::string variant) : variant_(std::move(variant)) {}

    FaceattrFactory(float threshold = 0.5f)
        : threshold_(threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<ClassificationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<AttributePostprocessor>(
            threshold_, AttributePostprocessor::LabelSet::CELEBA_40);
    }

    VisualizerPtr<ClassificationResult> createVisualizer() override {
        return std::make_unique<AttributeVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        threshold_ = config.get<float>("threshold", threshold_);
    }

    std::string getModelName() const override { return "Face_attr_ResNet_v1_18"; }
    std::string getTaskType() const override { return "attribute_recognition"; }

private:
    std::string variant_;
    float threshold_;
};

}  // namespace dxapp

#endif  // FACEATTR_FACTORY_HPP

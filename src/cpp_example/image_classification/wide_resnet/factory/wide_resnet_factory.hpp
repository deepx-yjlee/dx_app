/**
 * @file wide_resnet_factory.hpp
 * @brief WideResNet101_2 Abstract Factory implementation for classification
 */

#ifndef WIDE_RESNET_FACTORY_HPP
#define WIDE_RESNET_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/classification_postprocessor.hpp"
#include "common/visualizers/classification_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class WideResnetFactory : public IClassificationFactory {
public:
    /// The variant (a .dxnn stem) this factory should build for.
    /// Empty means the family default. Set from main(), which
    /// is the only place that sees argv.
    explicit WideResnetFactory(std::string variant) : variant_(std::move(variant)) {}

    WideResnetFactory(int num_classes = 1000, int top_k = 5)
        : num_classes_(num_classes), top_k_(top_k) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<ClassificationResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<EfficientNetPostprocessor>(num_classes_, top_k_);
    }

    VisualizerPtr<ClassificationResult> createVisualizer() override {
        return std::make_unique<ClassificationResultVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        num_classes_ = config.get<int>("num_classes", num_classes_);
        top_k_ = config.get<int>("top_k", top_k_);
    }

    std::string getModelName() const override { return "WideResNet101_2"; }
    std::string getTaskType() const override { return "classification"; }

private:
    std::string variant_;
    int num_classes_;
    int top_k_;
};

}  // namespace dxapp

#endif  // WIDE_RESNET_FACTORY_HPP

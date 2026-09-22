/**
 * @file yolov12_seg_factory.hpp
 * @brief Yolov12Seg Abstract Factory implementation
 */

#ifndef YOLOV12_SEG_FACTORY_HPP
#define YOLOV12_SEG_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

// Carried over from instance_segmentation/yolov8_seg: this family was added
// after the restructure, so it has no original factory of its own,
// and that family's postprocessing is what yolov12_seg needs. Only the
// class name, include guard and identity differ.

namespace dxapp {

class Yolov12SegFactory : public IInstanceSegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Yolov12SegFactory(float score_threshold = 0.5f, float nms_threshold = 0.65f)
        : score_threshold_(score_threshold), nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<InstanceSegmentationResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "yolov8-m-seg_640x640") {
        return std::make_unique<YOLOv8SegPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            is_ort_configured,
            80, class_names_
        );
            }
        if (variant_ == "yolov8-n-seg_640x640") {
        return std::make_unique<YOLOv8SegPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            is_ort_configured,
            80, class_names_
        );
            }
        if (variant_ == "yolov8-s-seg_640x640") {
        return std::make_unique<YOLOv8SegPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            is_ort_configured,
            80, class_names_
        );
            }
        // default: yolov8-l-seg_640x640
        return std::make_unique<YOLOv8SegPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            is_ort_configured);
    }

    VisualizerPtr<InstanceSegmentationResult> createVisualizer() override {
        return std::make_unique<InstanceSegmentationVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override { return "Yolov12Seg"; }
    std::string getTaskType() const override { return "instance_segmentation"; }

private:
    std::string variant_;
    std::vector<std::string> class_names_;  // from a sibling variant in this family
    float score_threshold_;
    float nms_threshold_;
};

}  // namespace dxapp

#endif  // YOLOV12_SEG_FACTORY_HPP

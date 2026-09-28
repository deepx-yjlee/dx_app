/**
 * @file yolov5_seg_factory.hpp
 * @brief YOLOv5-Seg Abstract Factory implementation
 * 
 * Uses v3-native YOLOv5Seg postprocessor (objectness + prototype masks).
 */

#ifndef YOLOV5_SEG_FACTORY_HPP
#define YOLOV5_SEG_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/segmentation_postprocessor.hpp"
#include "common/visualizers/segmentation_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Yolov5SegFactory : public IInstanceSegmentationFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Yolov5SegFactory(float obj_threshold = 0.25f,
                     float score_threshold = 0.25f,
                     float nms_threshold = 0.45f)
        : obj_threshold_(obj_threshold),
          score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<InstanceSegmentationResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "yolov5-x-seg_640x640") {
        return std::make_unique<YOLOv8SegPostprocessor>(
            input_width, input_height,
            score_threshold_, nms_threshold_,
            is_ort_configured);
            }
        // default: yolov5-l-seg_640x640
        (void)is_ort_configured;
        return std::make_unique<YOLOv5SegPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            80, 32, false, class_names_
        );
    }

    VisualizerPtr<InstanceSegmentationResult> createVisualizer() override {
        return std::make_unique<InstanceSegmentationVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        obj_threshold_ = config.get<float>("obj_threshold", obj_threshold_);
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        class_names_ = config.get_string_list("class_names");
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "YOLOv5-Seg" : variant_;
    }
    std::string getTaskType() const override { return "instance_segmentation"; }

private:
    std::string variant_;
    float obj_threshold_;
    float score_threshold_;
    float nms_threshold_;
    std::vector<std::string> class_names_;
};

}  // namespace dxapp

#endif  // YOLOV5_SEG_FACTORY_HPP

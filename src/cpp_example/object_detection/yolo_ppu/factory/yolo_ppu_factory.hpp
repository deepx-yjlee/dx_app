/**
 * @file yolo_ppu_factory.hpp
 * @brief YOLOv11N-PPU Abstract Factory implementation
 *
 * YOLOv11N PPU uses anchor-free decoding (same as YOLOv8 PPU).
 */

#ifndef YOLO_PPU_FACTORY_HPP
#define YOLO_PPU_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/ppu_postprocessor.hpp"
#include "common/visualizers/detection_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class YoloPpuFactory : public IDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    YoloPpuFactory(float obj_threshold = 0.25f,
                       float score_threshold = 0.4f,
                       float nms_threshold = 0.5f)
        : obj_threshold_(obj_threshold),
          score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<DetectionResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "yolov10-n_640x640_ppu") {
        return std::make_unique<YOLOv10PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov3-tiny_416x416_ppu") {
        return std::make_unique<YOLOv3TinyPPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov3_416x416_ppu") {
        return std::make_unique<YOLOv5PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov3_608x608_ppu") {
        return std::make_unique<YOLOv5PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov4_512x512_ppu") {
        return std::make_unique<YOLOv5PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov5-s_640x640_ppu") {
        return std::make_unique<YOLOv5PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov7-x_640x640_ppu") {
        return std::make_unique<YOLOv7PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolov7_640x640_ppu") {
        return std::make_unique<YOLOv7PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        if (variant_ == "yolox-s_640x640_ppu") {
        return std::make_unique<YOLOXPPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
            }
        // default: yolo11-n_640x640_ppu
        return std::make_unique<YOLOv8PPUPostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured,
            class_names_
        );
    }

    VisualizerPtr<DetectionResult> createVisualizer() override {
        return std::make_unique<DetectionVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        obj_threshold_ = config.get<float>("obj_threshold", obj_threshold_);
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        class_names_ = config.get_string_list("class_names");
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override { return "YOLOv11N-PPU"; }
    std::string getTaskType() const override { return "object_detection"; }

private:
    std::string variant_;
    float obj_threshold_;
    float score_threshold_;
    float nms_threshold_;
    std::vector<std::string> class_names_;
};

}  // namespace dxapp

#endif  // YOLO_PPU_FACTORY_HPP

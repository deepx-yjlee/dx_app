/**
 * @file yolov7_face_factory.hpp
 * @brief YOLOv5-Face Abstract Factory implementation for face detection
 */

#ifndef YOLOV7_FACE_FACTORY_HPP
#define YOLOV7_FACE_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/letterbox_preprocessor.hpp"
#include "common/processors/face_postprocessor.hpp"
#include "common/visualizers/face_visualizer.hpp"
#include "common/config/model_config.hpp"

#include <string>
#include <utility>

namespace dxapp {

class Yolov7FaceFactory : public IFaceDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    Yolov7FaceFactory(float obj_threshold = 0.25f,
                      float score_threshold = 0.25f,
                      float nms_threshold = 0.45f)
        : obj_threshold_(obj_threshold),
          score_threshold_(score_threshold),
          nms_threshold_(nms_threshold) {}

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<DetectionPreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<FaceDetectionResult> createPostprocessor(
        int input_width, int input_height, bool is_ort_configured = false) override {
        // Variant dispatch: these variants' ORIGINAL bodies are
        // spliced verbatim, so no behaviour is re-derived.
        if (variant_ == "yolov7-lite-t-face_640x640") {
        return std::make_unique<YOLOv5FacePostprocessor>(
            input_width, input_height, score_threshold_, nms_threshold_);
            }
        // default: yolov7-face_640x640
        return std::make_unique<YOLOv5FacePostprocessor>(
            input_width, input_height,
            obj_threshold_, score_threshold_, nms_threshold_,
            is_ort_configured
        );
    }

    VisualizerPtr<FaceDetectionResult> createVisualizer() override {
        return std::make_unique<FaceVisualizer>();
    }

    void loadConfig(const dxapp::ModelConfig& config) override {
        obj_threshold_ = config.get<float>("obj_threshold", obj_threshold_);
        score_threshold_ = config.get<float>("score_threshold", score_threshold_);
        nms_threshold_ = config.get<float>("nms_threshold", nms_threshold_);
    }

    std::string getModelName() const override { return "YOLOv7-Face"; }
    std::string getTaskType() const override { return "face_detection"; }

private:
    std::string variant_;
    float obj_threshold_;
    float score_threshold_;
    float nms_threshold_;
};

}  // namespace dxapp

#endif  // YOLOV7_FACE_FACTORY_HPP

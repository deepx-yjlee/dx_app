/**
 * @file npu_stage.hpp
 * @brief One variant factory plus the InferenceEngine that runs it.
 */

#ifndef DXAPP_MULTI_MODEL_NPU_STAGE_HPP
#define DXAPP_MULTI_MODEL_NPU_STAGE_HPP

#include "multi_model/pipeline.hpp"
#include "multi_model/stage_output.hpp"

#include "common/utility/common_util.hpp"

#include <dxrt/dxrt_api.h>

#include <memory>
#include <string>
#include <type_traits>

namespace dxapp {

template <typename Factory, typename Result>
PostprocessorPtr<Result> makePostprocessor(
    Factory* factory, int width, int height, bool ortConfigured, std::true_type) {
    return factory->createPostprocessor(width, height, ortConfigured);
}

template <typename Factory, typename Result>
PostprocessorPtr<Result> makePostprocessor(
    Factory* factory, int width, int height, bool, std::false_type) {
    return factory->createPostprocessor(width, height);
}

inline void fillMatching(StageOutput& output, const std::vector<DetectionResult>& results) {
    for (std::size_t i = 0; i < results.size(); ++i) {
        BoxRecord record;
        record.box = results[i].box;
        record.confidence = results[i].confidence;
        record.classId = results[i].class_id;
        record.className = results[i].class_name;
        output.boxes.push_back(record);
    }
}

inline void fillMatching(StageOutput& output, const std::vector<FaceDetectionResult>& results) {
    for (std::size_t i = 0; i < results.size(); ++i) {
        BoxRecord record;
        record.box = results[i].box;
        record.confidence = results[i].confidence;
        record.keypoints = results[i].landmarks;
        output.boxes.push_back(record);
    }
}

inline void fillMatching(StageOutput& output, const std::vector<PoseResult>& results) {
    for (std::size_t i = 0; i < results.size(); ++i) {
        BoxRecord record;
        record.box = results[i].box;
        record.confidence = results[i].confidence;
        record.keypoints = results[i].keypoints;
        output.boxes.push_back(record);
    }
}

inline void fillMatching(StageOutput& output, const std::vector<InstanceSegmentationResult>& results) {
    for (std::size_t i = 0; i < results.size(); ++i) {
        BoxRecord record;
        record.box = results[i].box;
        record.confidence = results[i].confidence;
        record.classId = results[i].class_id;
        record.className = results[i].class_name;
        if (!results[i].mask.empty()) {
            record.mask = results[i].mask.clone();
        }
        output.boxes.push_back(record);
    }
}

inline void fillMatching(StageOutput& output, const std::vector<DepthResult>& results) {
    if (!results.empty() && !results.front().depth_map.empty()) {
        output.depthMap = results.front().depth_map.clone();
    }
}

inline void fillMatching(StageOutput& output, const std::vector<EmbeddingResult>& results) {
    if (!results.empty()) {
        output.embedding = results.front().embedding;
    }
}

inline void fillMatching(StageOutput& output, const std::vector<HandLandmarkResult>& results) {
    for (std::size_t i = 0; i < results.size(); ++i) {
        BoxRecord record;
        record.confidence = results[i].confidence;
        record.className = results[i].handedness;
        record.keypoints = results[i].landmarks;
        output.boxes.push_back(record);
    }
}

template <typename Factory, typename Result, bool WithOrt>
class NpuStage : public IStage {
public:
    NpuStage(const std::string& stageId, const std::string& modelPath)
        : stageId_(stageId),
          modelPath_(modelPath),
          inputWidth_(0),
          inputHeight_(0),
          nhwc_(false),
          floatInput_(false),
          factory_(std::make_unique<Factory>()) {
        dxrt::InferenceOption option;
        engine_ = std::make_unique<dxrt::InferenceEngine>(modelPath, option);
        if (!minversionforRTandCompiler(engine_.get())) {
            throw PipelineError("dxrt version check failed for stage '" + stageId + "'");
        }
        if (engine_->GetInputs().empty()) {
            throw PipelineError("stage '" + stageId + "' model has no inputs: " + modelPath);
        }
        const std::vector<int64_t> inputShape = engine_->GetInputs().front().shape();
        parseInputShape(inputShape, inputWidth_, inputHeight_);
        nhwc_ = isInputNHWC(inputShape);
        floatInput_ = engine_->GetInputs().front().type() == dxrt::DataType::FLOAT;
        const bool ortConfigured = engine_->IsOrtConfigured();
        preprocessor_ = factory_->createPreprocessor(inputWidth_, inputHeight_);
        postprocessor_ = makePostprocessor<Factory, Result>(
            factory_.get(), inputWidth_, inputHeight_, ortConfigured,
            typename std::integral_constant<bool, WithOrt>::type());
    }

    StageOutput run(const cv::Mat& bgr) override {
        if (bgr.empty()) {
            throw PipelineError("stage '" + stageId_ + "' received an empty frame");
        }
        PreprocessContext context;
        cv::Mat preprocessed;
        preprocessor_->process(bgr, preprocessed, context);
        std::vector<float> floatBuffer;
        void* runData = preprocessed.data;
        if (floatInput_ && !preprocessed.empty()) {
            floatBuffer = convertToFloatBuffer(preprocessed, nhwc_);
            runData = floatBuffer.data();
        }
        const dxrt::TensorPtrs tensors = engine_->Run(runData, nullptr, nullptr);
        StageOutput output;
        if (tensors.empty()) {
            return output;
        }
        fillMatching(output, postprocessor_->process(tensors, context));
        return output;
    }

    int inputWidth() const { return inputWidth_; }
    int inputHeight() const { return inputHeight_; }

private:
    std::string stageId_;
    std::string modelPath_;
    int inputWidth_;
    int inputHeight_;
    bool nhwc_;
    bool floatInput_;
    std::unique_ptr<Factory> factory_;
    std::unique_ptr<dxrt::InferenceEngine> engine_;
    PreprocessorPtr preprocessor_;
    PostprocessorPtr<Result> postprocessor_;
};

}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_NPU_STAGE_HPP

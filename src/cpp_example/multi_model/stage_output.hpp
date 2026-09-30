/**
 * @file stage_output.hpp
 * @brief Common stage result used by every registered factory.
 *
 * C++14 has no std::variant, so boxes, a mask, a depth map, an embedding,
 * and a CPU head-pose share one struct. Unused fields stay empty.
 */

#ifndef DXAPP_MULTI_MODEL_STAGE_OUTPUT_HPP
#define DXAPP_MULTI_MODEL_STAGE_OUTPUT_HPP

#include "common/base/i_processor.hpp"

#include <string>
#include <vector>

namespace dxapp {

struct BoxRecord {
    std::vector<float> box;
    float confidence;
    int classId;
    std::string className;
    std::vector<Keypoint> keypoints;
    cv::Mat mask;

    BoxRecord() : confidence(0.0f), classId(-1) {}
};

struct StageOutput {
    std::vector<BoxRecord> boxes;
    cv::Mat depthMap;
    std::vector<float> embedding;
    bool hasHeadPose;
    double pitchDeg;
    double yawDeg;
    double rollDeg;

    StageOutput() : hasHeadPose(false), pitchDeg(0.0), yawDeg(0.0), rollDeg(0.0) {}
};

struct StageCall {
    // Crop rectangle in the source frame. Empty when the stage saw the full frame.
    std::vector<float> inputBox;
    StageOutput output;
};

class IStage {
public:
    virtual ~IStage() {}
    virtual StageOutput run(const cv::Mat& bgr) = 0;
};

}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_STAGE_OUTPUT_HPP

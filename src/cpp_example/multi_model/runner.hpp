/**
 * @file runner.hpp
 * @brief Execute a pipeline JSON file with registered NPU stages.
 */

#ifndef DXAPP_MULTI_MODEL_RUNNER_HPP
#define DXAPP_MULTI_MODEL_RUNNER_HPP

#include "multi_model/pipeline.hpp"
#include "multi_model/stage_output.hpp"

#include <map>
#include <memory>
#include <string>

namespace dxapp {

class MultiModelRunner {
public:
    MultiModelRunner(const std::string& pipelinePath, const std::string& modelsDir);

    // One BGR frame. The returned text is the fuse result.
    std::string runFrame(const cv::Mat& frame);

    const Pipeline& pipeline() const { return pipeline_; }

private:
    Pipeline pipeline_;
    std::map<std::string, std::unique_ptr<IStage>> stages_;
};

}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_RUNNER_HPP

/**
 * @file pipeline.hpp
 * @brief Declarative multi-model graph loaded from pipeline JSON.
 *
 * The JSON schema matches the Python loader in common/multi/pipeline.py.
 * A stage names an existing variant factory. depends_on and bind wire inputs.
 */

#ifndef DXAPP_MULTI_MODEL_PIPELINE_HPP
#define DXAPP_MULTI_MODEL_PIPELINE_HPP

#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace dxapp {

class PipelineError : public std::runtime_error {
public:
    explicit PipelineError(const std::string& message) : std::runtime_error(message) {}
};

struct BindSpec {
    std::string op;
    std::string source;
};

struct StageSpec {
    std::string id;
    int order;
    std::string kind;
    std::vector<std::string> dependsOn;
    bool hasBind;
    BindSpec bind;
    std::string task;
    std::string family;
    std::string variant;
    std::string model;
    std::string op;

    StageSpec() : order(0), hasBind(false) {}
};

struct Pipeline {
    std::string name;
    std::string fuse;
    std::vector<StageSpec> stages;
    // Numeric fuse parameters, for example scale_factor.
    std::map<std::string, double> fuseConfig;
    std::string path;
};

Pipeline loadPipeline(const std::string& path);

std::vector<std::vector<StageSpec>> executionWaves(const std::vector<StageSpec>& stages);

}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_PIPELINE_HPP

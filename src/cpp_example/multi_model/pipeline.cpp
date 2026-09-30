/**
 * @file pipeline.cpp
 * @brief Parse and validate a multi-model pipeline JSON file.
 */

#include "multi_model/pipeline.hpp"

#include "common/third_party/nlohmann_json.hpp"

#include <fstream>
#include <sstream>

namespace dxapp {
namespace {

std::string requireString(const nlohmann::json& object, const char* key, const std::string& where) {
    if (!object.contains(key) || !object.at(key).is_string()) {
        throw PipelineError(where + " field '" + key + "' must be a non-empty string");
    }
    const std::string value = object.at(key).get<std::string>();
    if (value.empty()) {
        throw PipelineError(where + " field '" + key + "' must be a non-empty string");
    }
    return value;
}

BindSpec parseBind(const std::string& stageId, const nlohmann::json& raw) {
    if (!raw.is_object()) {
        throw PipelineError("stage '" + stageId + "' bind must be an object");
    }
    BindSpec bind;
    bind.op = raw.value("op", "");
    bind.source = raw.value("source", "");
    if (bind.op.empty() || bind.source.empty()) {
        throw PipelineError("stage '" + stageId + "' bind needs op and source");
    }
    return bind;
}

StageSpec parseStage(const nlohmann::json& item, int index) {
    if (!item.is_object()) {
        throw PipelineError("stage[" + std::to_string(index) + "] must be an object");
    }
    StageSpec spec;
    spec.order = index;
    spec.id = requireString(item, "id", "stage[" + std::to_string(index) + "]");
    spec.kind = item.value("kind", "npu");
    if (spec.kind != "npu" && spec.kind != "cpu") {
        throw PipelineError("stage '" + spec.id + "' kind must be 'npu' or 'cpu'");
    }
    if (item.contains("depends_on") && !item.at("depends_on").is_null()) {
        const nlohmann::json& depends = item.at("depends_on");
        if (!depends.is_array()) {
            throw PipelineError("stage '" + spec.id + "' depends_on must be a list of stage ids");
        }
        for (nlohmann::json::const_iterator it = depends.begin(); it != depends.end(); ++it) {
            if (!it->is_string() || it->get<std::string>().empty()) {
                throw PipelineError("stage '" + spec.id + "' depends_on must be a list of stage ids");
            }
            spec.dependsOn.push_back(it->get<std::string>());
        }
    }
    if (item.contains("bind") && !item.at("bind").is_null()) {
        spec.bind = parseBind(spec.id, item.at("bind"));
        spec.hasBind = true;
        bool sourceListed = false;
        for (std::size_t i = 0; i < spec.dependsOn.size(); ++i) {
            if (spec.dependsOn[i] == spec.bind.source) {
                sourceListed = true;
                break;
            }
        }
        if (!sourceListed) {
            throw PipelineError(
                "stage '" + spec.id + "' bind source '" + spec.bind.source +
                "' must be listed in depends_on");
        }
    }
    spec.task = item.value("task", "");
    spec.family = item.value("family", "");
    spec.variant = item.value("variant", "");
    spec.op = item.value("op", "");
    if (spec.kind == "npu" && (spec.task.empty() || spec.family.empty() || spec.variant.empty())) {
        throw PipelineError("NPU stage '" + spec.id + "' needs task, family, and variant");
    }
    if (spec.kind == "cpu" && spec.op.empty()) {
        throw PipelineError("CPU stage '" + spec.id + "' needs op");
    }
    spec.model = item.value("model", "");
    if (spec.kind == "npu" && spec.model.empty()) {
        spec.model = spec.variant + ".dxnn";
    }
    return spec;
}

void validateGraph(const std::string& name, const std::vector<StageSpec>& stages) {
    std::map<std::string, int> seen;
    for (std::size_t i = 0; i < stages.size(); ++i) {
        if (seen.count(stages[i].id) != 0) {
            throw PipelineError("pipeline '" + name + "' repeats stage id '" + stages[i].id + "'");
        }
        seen[stages[i].id] = 1;
    }
    for (std::size_t i = 0; i < stages.size(); ++i) {
        for (std::size_t d = 0; d < stages[i].dependsOn.size(); ++d) {
            if (seen.count(stages[i].dependsOn[d]) == 0) {
                throw PipelineError(
                    "stage '" + stages[i].id + "' depends on unknown stage '" +
                    stages[i].dependsOn[d] + "'");
            }
        }
    }
    executionWaves(stages);
}

std::map<std::string, double> parseFuseConfig(const std::string& name, const nlohmann::json& payload) {
    std::map<std::string, double> config;
    if (!payload.contains("fuse_config") || payload.at("fuse_config").is_null()) {
        return config;
    }
    const nlohmann::json& raw = payload.at("fuse_config");
    if (!raw.is_object()) {
        throw PipelineError("pipeline '" + name + "' fuse_config must be an object");
    }
    for (nlohmann::json::const_iterator it = raw.begin(); it != raw.end(); ++it) {
        if (!it.value().is_number()) {
            throw PipelineError("pipeline '" + name + "' fuse_config." + it.key() + " must be a number");
        }
        config[it.key()] = it.value().get<double>();
    }
    return config;
}

}  // namespace

std::vector<std::vector<StageSpec>> executionWaves(const std::vector<StageSpec>& stages) {
    std::map<std::string, StageSpec> pending;
    for (std::size_t i = 0; i < stages.size(); ++i) {
        pending[stages[i].id] = stages[i];
    }
    std::map<std::string, int> finished;
    std::vector<std::vector<StageSpec>> waves;
    while (!pending.empty()) {
        std::vector<StageSpec> ready;
        for (std::map<std::string, StageSpec>::const_iterator it = pending.begin();
             it != pending.end(); ++it) {
            bool depsDone = true;
            for (std::size_t d = 0; d < it->second.dependsOn.size(); ++d) {
                if (finished.count(it->second.dependsOn[d]) == 0) {
                    depsDone = false;
                    break;
                }
            }
            if (depsDone) {
                ready.push_back(it->second);
            }
        }
        if (ready.empty()) {
            std::string names;
            for (std::map<std::string, StageSpec>::const_iterator it = pending.begin();
                 it != pending.end(); ++it) {
                if (!names.empty()) {
                    names += ", ";
                }
                names += it->first;
            }
            throw PipelineError("pipeline graph has a cycle or a missing dependency: " + names);
        }
        // Declaration order, not map order.
        for (std::size_t i = 0; i < ready.size(); ++i) {
            for (std::size_t j = i + 1; j < ready.size(); ++j) {
                if (ready[j].order < ready[i].order) {
                    std::swap(ready[i], ready[j]);
                }
            }
        }
        for (std::size_t i = 0; i < ready.size(); ++i) {
            finished[ready[i].id] = 1;
            pending.erase(ready[i].id);
        }
        waves.push_back(ready);
    }
    return waves;
}

Pipeline loadPipeline(const std::string& path) {
    std::ifstream input(path.c_str());
    if (!input) {
        throw PipelineError("cannot open pipeline: " + path);
    }
    nlohmann::json payload;
    try {
        input >> payload;
    } catch (const nlohmann::json::exception& exc) {
        throw PipelineError(path + " is not valid JSON: " + exc.what());
    }
    if (!payload.is_object()) {
        throw PipelineError(path + " must contain a JSON object");
    }
    Pipeline pipeline;
    pipeline.path = path;
    pipeline.name = requireString(payload, "name", "pipeline");
    pipeline.fuse = requireString(payload, "fuse", "pipeline");
    if (!payload.contains("stages") || !payload.at("stages").is_array() || payload.at("stages").empty()) {
        throw PipelineError("pipeline '" + pipeline.name + "' needs a non-empty stages list");
    }
    const nlohmann::json& rawStages = payload.at("stages");
    int index = 0;
    for (nlohmann::json::const_iterator it = rawStages.begin(); it != rawStages.end(); ++it, ++index) {
        pipeline.stages.push_back(parseStage(*it, index));
    }
    pipeline.fuseConfig = parseFuseConfig(pipeline.name, payload);
    validateGraph(pipeline.name, pipeline.stages);
    return pipeline;
}

}  // namespace dxapp

/**
 * @file registry.hpp
 * @brief Compile-time registry of the variant factories a pipeline may name.
 */

#ifndef DXAPP_MULTI_MODEL_REGISTRY_HPP
#define DXAPP_MULTI_MODEL_REGISTRY_HPP

#include "multi_model/stage_output.hpp"

#include <memory>
#include <string>

namespace dxapp {

std::unique_ptr<IStage> createRegisteredStage(
    const std::string& task,
    const std::string& family,
    const std::string& variant,
    const std::string& stageId,
    const std::string& modelPath);

}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_REGISTRY_HPP

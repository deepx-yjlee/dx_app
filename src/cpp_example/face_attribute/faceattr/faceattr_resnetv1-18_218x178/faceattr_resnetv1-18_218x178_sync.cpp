/**
 * @file faceattr_resnetv1-18_218x178
 * @brief faceattr sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/faceattr_resnetv1-18_218x178_factory.hpp"
#include "common/runner/sync_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::FaceattrFactory>();
    dxapp::SyncClassificationRunner<dxapp::FaceattrFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

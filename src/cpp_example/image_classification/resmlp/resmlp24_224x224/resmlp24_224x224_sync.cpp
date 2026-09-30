/**
 * @file resmlp24_224x224
 * @brief resmlp sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/resmlp24_224x224_factory.hpp"
#include "common/runner/sync_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::ResmlpFactory>();
    dxapp::SyncClassificationRunner<dxapp::ResmlpFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

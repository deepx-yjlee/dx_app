/**
 * @file regnet-x1.6gf_224x224_v1
 * @brief regnet sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/regnet-x1.6gf_224x224_v1_factory.hpp"
#include "common/runner/sync_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::RegnetFactory>();
    dxapp::SyncClassificationRunner<dxapp::RegnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

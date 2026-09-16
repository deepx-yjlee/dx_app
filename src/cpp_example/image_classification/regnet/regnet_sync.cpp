/**
 * @file regnet_sync.cpp
 * @brief regnet sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/regnet_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::RegnetFactory>(variant);
    dxapp::SyncClassificationRunner<dxapp::RegnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

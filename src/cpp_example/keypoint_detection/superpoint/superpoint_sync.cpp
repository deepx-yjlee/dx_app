/**
 * @file superpoint_sync.cpp
 * @brief superpoint sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/superpoint_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_keypoint_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::SuperpointFactory>(variant);
    dxapp::SyncKeypointRunner<dxapp::SuperpointFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

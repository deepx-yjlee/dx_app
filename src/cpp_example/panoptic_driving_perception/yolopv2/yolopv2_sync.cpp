/**
 * @file yolopv2_sync.cpp
 * @brief yolopv2 sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolopv2_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_panoptic_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolopv2Factory>(variant);
    dxapp::SyncPanopticRunner<dxapp::Yolopv2Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

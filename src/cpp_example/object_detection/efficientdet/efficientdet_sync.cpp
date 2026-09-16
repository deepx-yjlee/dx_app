/**
 * @file efficientdet_sync.cpp
 * @brief efficientdet sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/efficientdet_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::EfficientdetFactory>(variant);
    dxapp::SyncDetectionRunner<dxapp::EfficientdetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

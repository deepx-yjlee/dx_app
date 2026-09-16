/**
 * @file yolo26_sync.cpp
 * @brief yolo26 sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolo26_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolo26Factory>(variant);
    dxapp::SyncDetectionRunner<dxapp::Yolo26Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

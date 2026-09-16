/**
 * @file yolov6_sync.cpp
 * @brief yolov6 sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov6_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolov6Factory>(variant);
    dxapp::SyncDetectionRunner<dxapp::Yolov6Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

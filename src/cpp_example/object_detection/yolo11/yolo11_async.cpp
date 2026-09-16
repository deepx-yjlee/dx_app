/**
 * @file yolo11_async.cpp
 * @brief yolo11 async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolo11_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolo11Factory>(variant);
    dxapp::AsyncDetectionRunner<dxapp::Yolo11Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

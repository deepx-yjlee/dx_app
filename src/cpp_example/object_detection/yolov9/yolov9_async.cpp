/**
 * @file yolov9_async.cpp
 * @brief yolov9 async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov9_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolov9Factory>(variant);
    dxapp::AsyncDetectionRunner<dxapp::Yolov9Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

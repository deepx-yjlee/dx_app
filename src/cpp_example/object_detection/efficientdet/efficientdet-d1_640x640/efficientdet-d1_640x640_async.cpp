/**
 * @file efficientdet-d1_640x640
 * @brief efficientdet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/efficientdet-d1_640x640_factory.hpp"
#include "common/runner/async_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::EfficientdetFactory>();
    dxapp::AsyncDetectionRunner<dxapp::EfficientdetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

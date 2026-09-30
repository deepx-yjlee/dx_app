/**
 * @file yolov8-l-seg_640x640
 * @brief yolov8_seg async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov8-l-seg_640x640_factory.hpp"
#include "common/runner/async_segmentation_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::Yolov8SegFactory>();
    dxapp::AsyncInstanceSegRunner<dxapp::Yolov8SegFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

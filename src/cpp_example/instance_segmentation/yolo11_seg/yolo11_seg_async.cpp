/**
 * @file yolo11_seg_async.cpp
 * @brief yolo11_seg async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolo11_seg_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_segmentation_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolo11SegFactory>(variant);
    dxapp::AsyncInstanceSegRunner<dxapp::Yolo11SegFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

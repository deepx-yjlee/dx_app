/**
 * @file yolov5_face_async.cpp
 * @brief yolov5_face async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov5_face_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_face_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolov5FaceFactory>(variant);
    dxapp::AsyncFaceRunner<dxapp::Yolov5FaceFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

/**
 * @file yolov7_face_sync.cpp
 * @brief yolov7_face sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov7_face_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_face_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolov7FaceFactory>(variant);
    dxapp::SyncFaceRunner<dxapp::Yolov7FaceFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

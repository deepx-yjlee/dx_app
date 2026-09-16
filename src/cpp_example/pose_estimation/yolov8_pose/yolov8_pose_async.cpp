/**
 * @file yolov8_pose_async.cpp
 * @brief yolov8_pose async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolov8_pose_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_pose_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolov8PoseFactory>(variant);
    dxapp::AsyncPoseRunner<dxapp::Yolov8PoseFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

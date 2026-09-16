/**
 * @file yolo26_pose_sync.cpp
 * @brief yolo26_pose sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolo26_pose_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_pose_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Yolo26PoseFactory>(variant);
    dxapp::SyncPoseRunner<dxapp::Yolo26PoseFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

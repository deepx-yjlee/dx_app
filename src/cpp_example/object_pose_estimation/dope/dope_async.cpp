/**
 * @file dope_async.cpp
 * @brief dope async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/dope_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_object_pose_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::DopeFactory>(variant);
    dxapp::AsyncObjectPoseRunner<dxapp::DopeFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

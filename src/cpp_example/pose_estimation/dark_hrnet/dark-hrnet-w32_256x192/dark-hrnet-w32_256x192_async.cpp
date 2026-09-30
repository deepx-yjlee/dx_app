/**
 * @file dark-hrnet-w32_256x192
 * @brief dark_hrnet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/dark-hrnet-w32_256x192_factory.hpp"
#include "common/runner/async_pose_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::DarkHrnetFactory>();
    dxapp::AsyncPoseRunner<dxapp::DarkHrnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

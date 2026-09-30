/**
 * @file unet_mobilenetv2_256x256
 * @brief unet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/unet_mobilenetv2_256x256_factory.hpp"
#include "common/runner/async_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::UnetFactory>();
    dxapp::AsyncSemanticSegRunner<dxapp::UnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

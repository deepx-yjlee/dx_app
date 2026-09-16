/**
 * @file unet_async.cpp
 * @brief unet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/unet_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::UnetFactory>(variant);
    dxapp::AsyncSemanticSegRunner<dxapp::UnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

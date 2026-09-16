/**
 * @file hardnet_async.cpp
 * @brief hardnet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/hardnet_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::HardnetFactory>(variant);
    dxapp::AsyncClassificationRunner<dxapp::HardnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

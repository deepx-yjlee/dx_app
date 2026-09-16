/**
 * @file shufflenetv2_async.cpp
 * @brief shufflenetv2 async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/shufflenetv2_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::Shufflenetv2Factory>(variant);
    dxapp::AsyncClassificationRunner<dxapp::Shufflenetv2Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

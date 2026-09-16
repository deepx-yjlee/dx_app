/**
 * @file resnext_async.cpp
 * @brief resnext async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/resnext_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::ResnextFactory>(variant);
    dxapp::AsyncClassificationRunner<dxapp::ResnextFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

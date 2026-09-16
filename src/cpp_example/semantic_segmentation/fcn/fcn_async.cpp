/**
 * @file fcn_async.cpp
 * @brief fcn async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/fcn_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::FcnFactory>(variant);
    dxapp::AsyncSemanticSegRunner<dxapp::FcnFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

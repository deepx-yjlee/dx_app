/**
 * @file segformer_async.cpp
 * @brief segformer async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/segformer_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::SegformerFactory>(variant);
    dxapp::AsyncSemanticSegRunner<dxapp::SegformerFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

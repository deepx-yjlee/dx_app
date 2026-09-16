/**
 * @file casvit_seg_sync.cpp
 * @brief casvit_seg sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/casvit_seg_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::CasvitSegFactory>(variant);
    dxapp::SyncSemanticSegRunner<dxapp::CasvitSegFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

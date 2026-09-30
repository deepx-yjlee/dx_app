/**
 * @file casvit-t-fpn-resnet50_512x512
 * @brief casvit_seg sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/casvit-t-fpn-resnet50_512x512_factory.hpp"
#include "common/runner/sync_semantic_seg_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::CasvitSegFactory>();
    dxapp::SyncSemanticSegRunner<dxapp::CasvitSegFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

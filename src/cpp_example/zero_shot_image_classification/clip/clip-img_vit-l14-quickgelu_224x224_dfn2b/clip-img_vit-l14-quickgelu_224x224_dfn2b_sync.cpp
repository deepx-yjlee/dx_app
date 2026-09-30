/**
 * @file clip-img_vit-l14-quickgelu_224x224_dfn2b
 * @brief clip sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/clip-img_vit-l14-quickgelu_224x224_dfn2b_factory.hpp"
#include "common/runner/sync_embedding_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::ClipFactory>();
    dxapp::SyncEmbeddingRunner<dxapp::ClipFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

/**
 * @file vit-l-p16_512x512_swag
 * @brief vit sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/vit-l-p16_512x512_swag_factory.hpp"
#include "common/runner/sync_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::VitFactory>();
    dxapp::SyncClassificationRunner<dxapp::VitFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

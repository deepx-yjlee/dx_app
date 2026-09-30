/**
 * @file efficientnet-b5_456x456
 * @brief efficientnet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/efficientnet-b5_456x456_factory.hpp"
#include "common/runner/async_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::EfficientnetFactory>();
    dxapp::AsyncClassificationRunner<dxapp::EfficientnetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

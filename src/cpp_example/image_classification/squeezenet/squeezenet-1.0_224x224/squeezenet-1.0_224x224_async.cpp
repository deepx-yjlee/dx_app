/**
 * @file squeezenet-1.0_224x224
 * @brief squeezenet async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/squeezenet-1.0_224x224_factory.hpp"
#include "common/runner/async_classification_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::SqueezenetFactory>();
    dxapp::AsyncClassificationRunner<dxapp::SqueezenetFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

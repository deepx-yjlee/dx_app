/**
 * @file yolact_regnet-x1.6gf_512x512
 * @brief yolact async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolact_regnet-x1.6gf_512x512_factory.hpp"
#include "common/runner/async_segmentation_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::YolactFactory>();
    dxapp::AsyncInstanceSegRunner<dxapp::YolactFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

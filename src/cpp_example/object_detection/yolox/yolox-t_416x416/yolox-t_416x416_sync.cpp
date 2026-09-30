/**
 * @file yolox-t_416x416
 * @brief yolox sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolox-t_416x416_factory.hpp"
#include "common/runner/sync_detection_runner.hpp"

int main(int argc, char* argv[]) {
    auto factory = std::make_unique<dxapp::YoloxFactory>();
    dxapp::SyncDetectionRunner<dxapp::YoloxFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

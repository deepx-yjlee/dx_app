/**
 * @file realesrgan_sync.cpp
 * @brief realesrgan sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/realesrgan_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_restoration_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::RealesrganFactory>(variant);
    dxapp::SyncRestorationRunner<dxapp::RealesrganFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

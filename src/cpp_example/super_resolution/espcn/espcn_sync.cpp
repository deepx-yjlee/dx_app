/**
 * @file espcn_sync.cpp
 * @brief espcn sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/espcn_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_restoration_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::EspcnFactory>(variant);
    dxapp::SyncRestorationRunner<dxapp::EspcnFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

/**
 * @file dncnn_sync.cpp
 * @brief dncnn sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/dncnn_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_restoration_runner.hpp"

int main(int argc, char* argv[]) {
    // Default-construct so the factory's own member initialisation runs, THEN select
    // the variant. Passing the variant to a constructor would bypass that.
    auto factory = std::make_unique<dxapp::DncnnFactory>();
    factory->setVariant(dxapp::variantFromArgs(argc, argv));
    dxapp::SyncRestorationRunner<dxapp::DncnnFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

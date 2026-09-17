/**
 * @file yolopv2_sync.cpp
 * @brief yolopv2 sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/yolopv2_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_panoptic_runner.hpp"

int main(int argc, char* argv[]) {
    // Default-construct so the factory's own member initialisation runs, THEN select
    // the variant. Passing the variant to a constructor would bypass that.
    auto factory = std::make_unique<dxapp::Yolopv2Factory>();
    factory->setVariant(dxapp::variantFromArgs(argc, argv));
    dxapp::SyncPanopticRunner<dxapp::Yolopv2Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

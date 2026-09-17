/**
 * @file 3ddfa_v2_async.cpp
 * @brief 3ddfa_v2 async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/3ddfa_v2_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_face_alignment_runner.hpp"

int main(int argc, char* argv[]) {
    // Default-construct so the factory's own member initialisation runs, THEN select
    // the variant. Passing the variant to a constructor would bypass that.
    auto factory = std::make_unique<dxapp::N3ddfaV2Factory>();
    factory->setVariant(dxapp::variantFromArgs(argc, argv));
    dxapp::AsyncFaceAlignmentRunner<dxapp::N3ddfaV2Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

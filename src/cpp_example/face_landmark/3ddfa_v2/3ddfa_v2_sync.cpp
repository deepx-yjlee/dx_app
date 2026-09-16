/**
 * @file 3ddfa_v2_sync.cpp
 * @brief 3ddfa_v2 sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/3ddfa_v2_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_face_alignment_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::N3ddfaV2Factory>(variant);
    dxapp::SyncFaceAlignmentRunner<dxapp::N3ddfaV2Factory> runner(std::move(factory));
    return runner.run(argc, argv);
}

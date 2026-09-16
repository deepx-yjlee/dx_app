/**
 * @file mediapipe_hands_lite_sync.cpp
 * @brief mediapipe_hands_lite sync inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/mediapipe_hands_lite_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/sync_hand_landmark_runner.hpp"

int main(int argc, char* argv[]) {
    auto variant = dxapp::variantFromArgs(argc, argv);
    auto factory = std::make_unique<dxapp::MediapipeHandsLiteFactory>(variant);
    dxapp::SyncHandLandmarkRunner<dxapp::MediapipeHandsLiteFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

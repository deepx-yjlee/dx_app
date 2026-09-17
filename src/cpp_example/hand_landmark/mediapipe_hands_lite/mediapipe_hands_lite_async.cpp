/**
 * @file mediapipe_hands_lite_async.cpp
 * @brief mediapipe_hands_lite async inference -- one entry point for the whole family.
 *
 * The variant is the .dxnn stem, so the model path alone identifies it and no
 * --variant flag or runner change is needed.
 */

#include "factory/mediapipe_hands_lite_factory.hpp"
#include "common/utility/variant_from_args.hpp"
#include "common/runner/async_hand_landmark_runner.hpp"

int main(int argc, char* argv[]) {
    // Default-construct so the factory's own member initialisation runs, THEN select
    // the variant. Passing the variant to a constructor would bypass that.
    auto factory = std::make_unique<dxapp::MediapipeHandsLiteFactory>();
    factory->setVariant(dxapp::variantFromArgs(argc, argv));
    dxapp::AsyncHandLandmarkRunner<dxapp::MediapipeHandsLiteFactory> runner(std::move(factory));
    return runner.run(argc, argv);
}

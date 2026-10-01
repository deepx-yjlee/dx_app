/**
 * @file hand_cascade_probe.cpp
 * @brief Palm crops and hand landmarks, in frame coordinates, from the
 *        multi_model runtime's own stages.
 *
 *   hand_cascade_probe --pipeline <hand_cascade/pipeline.json> --image <frame>
 *                      --models-dir <dir>
 *
 * multi_model_run prints only a count line (event=... palms=N hands=M). The
 * graph test (test_hand_cascade_graph_matches_the_pipeline_runtime) needs the
 * landmark coordinates too, so this probe:
 *
 *   1. runs MultiModelRunner::runFrame on the frame and keeps its count line;
 *   2. builds the same two stages through dxapp::createRegisteredStage (the
 *      public registry.hpp API) and runs palm -> crops -> landmarks. The crops
 *      are cut by PaddedCropRect (common/utility/roi_crop.hpp), as
 *      cropBoxes() in multi_model/runner.cpp cuts them (it sits in an
 *      anonymous namespace there); the graph engine's RouteRois crops by the
 *      same header;
 *   3. fails unless its own palm and hand counts equal the count line, which
 *      ties its crops to the real runner;
 *   4. prints one JSON object: per palm, the crop box and the landmarks in
 *      frame coordinates (x + crop.left, y + crop.top).
 *
 * Test-only. It links multi_model/{pipeline,registry,runner}.cpp unchanged.
 */

#include "multi_model/pipeline.hpp"
#include "multi_model/registry.hpp"
#include "multi_model/runner.hpp"

#include "common/third_party/nlohmann_json.hpp"
#include "common/utility/roi_crop.hpp"

#include <opencv2/imgcodecs.hpp>

#include <algorithm>
#include <cstdio>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {

// Sends std::cout to std::cerr for its lifetime, so stdout carries the JSON
// report only. The runner and the stages print progress lines on stdout.
class StdoutToStderr {
public:
    StdoutToStderr() : saved_(std::cout.rdbuf(std::cerr.rdbuf())) {}
    ~StdoutToStderr() { std::cout.rdbuf(saved_); }
    StdoutToStderr(const StdoutToStderr&) = delete;
    StdoutToStderr& operator=(const StdoutToStderr&) = delete;

private:
    std::streambuf* saved_;
};

struct Options {
    std::string pipeline;
    std::string image;
    std::string modelsDir;
};

struct ProbeCrop {
    std::size_t palmIndex;   // index of the palm box the crop was cut from
    std::vector<float> box;  // left, top, right, bottom in frame pixels
    cv::Mat image;
};

bool takeValue(int argc, char** argv, int& index, std::string& slot) {
    if (index + 1 >= argc) {
        return false;
    }
    ++index;
    slot = argv[index];
    return true;
}

bool parseArgs(int argc, char** argv, Options& options) {
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        std::string* slot = nullptr;
        if (arg == "--pipeline") {
            slot = &options.pipeline;
        } else if (arg == "--image") {
            slot = &options.image;
        } else if (arg == "--models-dir") {
            slot = &options.modelsDir;
        } else {
            std::cerr << "unknown argument: " << arg << std::endl;
            return false;
        }
        if (!takeValue(argc, argv, i, *slot)) {
            std::cerr << arg << " needs a value" << std::endl;
            return false;
        }
    }
    return !options.pipeline.empty() && !options.image.empty() && !options.modelsDir.empty();
}

// Same as boxArea() in multi_model/runner.cpp: fuseHand counts a palm only
// when its box has a positive area.
double boxArea(const std::vector<float>& box) {
    if (box.size() < 4) {
        return 0.0;
    }
    const double width = std::max(0.0, static_cast<double>(box[2]) - static_cast<double>(box[0]));
    const double height = std::max(0.0, static_cast<double>(box[3]) - static_cast<double>(box[1]));
    return width * height;
}

// The runner's crops (cropBoxes() in multi_model/runner.cpp): the detector
// box as x, y, x2 - x, y2 - y through PaddedCropRect; a crop with no whole
// pixel is skipped. bind "roi" passes padRatio 0.
std::vector<ProbeCrop> cropLikeTheRunner(
    const cv::Mat& frame, const std::vector<dxapp::BoxRecord>& records, float padRatio) {
    std::vector<ProbeCrop> crops;
    for (std::size_t i = 0; i < records.size(); ++i) {
        const std::vector<float>& raw = records[i].box;
        if (raw.size() < 4) {
            continue;
        }
        const cv::Rect2f box(raw[0], raw[1], raw[2] - raw[0], raw[3] - raw[1]);
        const cv::Rect rect = dxapp::PaddedCropRect(box, padRatio, frame.cols, frame.rows);
        if (rect.width <= 0 || rect.height <= 0) {
            continue;
        }
        ProbeCrop crop;
        crop.palmIndex = i;
        crop.box.push_back(static_cast<float>(rect.x));
        crop.box.push_back(static_cast<float>(rect.y));
        crop.box.push_back(static_cast<float>(rect.x + rect.width));
        crop.box.push_back(static_cast<float>(rect.y + rect.height));
        crop.image = frame(rect).clone();
        crops.push_back(crop);
    }
    return crops;
}

// The landmark stage's hands on one crop, moved into frame coordinates.
nlohmann::json handsInFrame(dxapp::IStage& stage, const ProbeCrop& crop) {
    const dxapp::StageOutput hands = stage.run(crop.image);
    const float left = crop.box[0];
    const float top = crop.box[1];
    nlohmann::json handsJson = nlohmann::json::array();
    for (std::size_t h = 0; h < hands.boxes.size(); ++h) {
        const dxapp::BoxRecord& hand = hands.boxes[h];
        nlohmann::json landmarks = nlohmann::json::array();
        for (std::size_t k = 0; k < hand.keypoints.size(); ++k) {
            nlohmann::json point = nlohmann::json::array();
            point.push_back(hand.keypoints[k].x + left);
            point.push_back(hand.keypoints[k].y + top);
            landmarks.push_back(point);
        }
        nlohmann::json handJson = nlohmann::json::object();
        handJson["confidence"] = hand.confidence;
        handJson["handedness"] = hand.className;
        handJson["landmarks"] = landmarks;
        handsJson.push_back(handJson);
    }
    return handsJson;
}

bool parseCountLine(const std::string& line, int& palms, int& hands) {
    const std::string::size_type at = line.find(" palms=");
    if (at == std::string::npos) {
        return false;
    }
    return std::sscanf(line.c_str() + at, " palms=%d hands=%d", &palms, &hands) == 2;
}

std::string joinPath(const std::string& dir, const std::string& file) {
    if (dir.empty() || dir[dir.size() - 1] == '/') {
        return dir + file;
    }
    return dir + "/" + file;
}

// The palm stage (no bind) and the landmark stage (bind roi on the palm).
bool findStages(const dxapp::Pipeline& pipeline, dxapp::StageSpec& palm, dxapp::StageSpec& landmark) {
    if (pipeline.stages.size() != 2) {
        return false;
    }
    const dxapp::StageSpec& first = pipeline.stages[0];
    const dxapp::StageSpec& second = pipeline.stages[1];
    const bool firstIsPalm = !first.hasBind;
    palm = firstIsPalm ? first : second;
    landmark = firstIsPalm ? second : first;
    return palm.kind == "npu" && landmark.kind == "npu" && !palm.hasBind && landmark.hasBind &&
           landmark.bind.op == "roi" && landmark.bind.source == palm.id;
}

nlohmann::json boxJson(const std::vector<float>& box) {
    nlohmann::json out = nlohmann::json::array();
    for (std::size_t i = 0; i < box.size(); ++i) {
        out.push_back(box[i]);
    }
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    Options options;
    if (!parseArgs(argc, argv, options)) {
        std::cerr << "usage: hand_cascade_probe --pipeline <pipeline.json> --image <frame>"
                  << " --models-dir <dir>" << std::endl;
        return 1;
    }
    try {
        const cv::Mat frame = cv::imread(options.image, cv::IMREAD_COLOR);
        if (frame.empty()) {
            std::cerr << "cannot read image: " << options.image << std::endl;
            return 1;
        }

        // 1. The real runner's count line. The runner's own stage-ready lines
        //    go to stdout, so they are sent to stderr to keep stdout JSON only.
        std::string countLine;
        {
            const StdoutToStderr quiet;
            dxapp::MultiModelRunner runner(options.pipeline, options.modelsDir);
            countLine = runner.runFrame(frame);
        }
        int runnerPalms = -1;
        int runnerHands = -1;
        if (!parseCountLine(countLine, runnerPalms, runnerHands)) {
            std::cerr << "runner printed no count line: " << countLine << std::endl;
            return 1;
        }

        // 2. The same two stages through the public registry API.
        const dxapp::Pipeline pipeline = dxapp::loadPipeline(options.pipeline);
        dxapp::StageSpec palmSpec;
        dxapp::StageSpec landmarkSpec;
        if (!findStages(pipeline, palmSpec, landmarkSpec)) {
            std::cerr << "expected two npu stages: a palm stage and a landmark stage bound to it by roi"
                      << std::endl;
            return 1;
        }
        // Each stage loads its variant's config.json, which reports on stdout.
        std::unique_ptr<dxapp::IStage> palmStage;
        std::unique_ptr<dxapp::IStage> landmarkStage;
        {
            const StdoutToStderr quiet;
            palmStage = dxapp::createRegisteredStage(
                palmSpec.task, palmSpec.family, palmSpec.variant, palmSpec.id,
                joinPath(options.modelsDir, palmSpec.model));
            landmarkStage = dxapp::createRegisteredStage(
                landmarkSpec.task, landmarkSpec.family, landmarkSpec.variant, landmarkSpec.id,
                joinPath(options.modelsDir, landmarkSpec.model));
        }

        const dxapp::StageOutput palms = palmStage->run(frame);
        int palmCount = 0;
        for (std::size_t i = 0; i < palms.boxes.size(); ++i) {
            if (boxArea(palms.boxes[i].box) > 0.0) {
                ++palmCount;
            }
        }
        const std::vector<ProbeCrop> crops = cropLikeTheRunner(frame, palms.boxes, 0.f);

        nlohmann::json report = nlohmann::json::object();
        report["count_line"] = countLine;
        report["palms"] = palmCount;
        report["hands"] = static_cast<int>(crops.size());
        nlohmann::json palmBoxes = nlohmann::json::array();
        for (std::size_t i = 0; i < palms.boxes.size(); ++i) {
            nlohmann::json entry = nlohmann::json::object();
            entry["box"] = boxJson(palms.boxes[i].box);
            entry["score"] = palms.boxes[i].confidence;
            palmBoxes.push_back(entry);
        }
        report["palm_boxes"] = palmBoxes;

        // 3. Landmarks per crop, moved into frame coordinates.
        nlohmann::json cropsJson = nlohmann::json::array();
        for (std::size_t i = 0; i < crops.size(); ++i) {
            nlohmann::json cropJson = nlohmann::json::object();
            cropJson["palm_index"] = static_cast<int>(crops[i].palmIndex);
            cropJson["crop"] = boxJson(crops[i].box);
            cropJson["hands"] = handsInFrame(*landmarkStage, crops[i]);
            cropsJson.push_back(cropJson);
        }
        report["crops"] = cropsJson;

        std::cout << report.dump(2) << std::endl;

        // 4. The probe's crops must reproduce the runner's counts.
        if (palmCount != runnerPalms || static_cast<int>(crops.size()) != runnerHands) {
            std::cerr << "probe counts palms=" << palmCount << " hands=" << crops.size()
                      << " differ from the runner's line: " << countLine << std::endl;
            return 2;
        }
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "hand_cascade_probe: " << exc.what() << std::endl;
        return 1;
    }
}

/**
 * @file main.cpp
 * @brief Run one pipeline JSON file on one image.
 *
 *   multi_model_run --pipeline <pipeline.json> --image <frame> [--models-dir DIR] [--save PATH]
 */

#include "multi_model/runner.hpp"

#include <opencv2/imgcodecs.hpp>

#include <iostream>
#include <string>

namespace {

struct Options {
    std::string pipeline;
    std::string image;
    std::string modelsDir;
    std::string savePath;
    bool help;
    Options() : help(false) {}
};

void printUsage() {
    std::cout
        << "Usage: multi_model_run --pipeline <pipeline.json> --image <frame>\n"
        << "         [--models-dir DIR] [--save PATH]\n"
        << "\n"
        << "Pipelines:\n"
        << "  src/cpp_example/multi_model/hand_cascade/pipeline.json\n"
        << "  src/cpp_example/multi_model/logistics_volume/pipeline.json\n"
        << "  src/cpp_example/multi_model/worker_safety/pipeline.json\n"
        << "  src/cpp_example/multi_model/dms_clip/pipeline.json\n";
}

bool takeValue(int argc, char** argv, int& index, std::string& slot) {
    if (index + 1 >= argc) {
        return false;
    }
    ++index;
    slot = argv[index];
    return true;
}

Options parseArgs(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            options.help = true;
        } else if (arg == "--pipeline" && !takeValue(argc, argv, i, options.pipeline)) {
            throw dxapp::PipelineError("--pipeline needs a path");
        } else if (arg == "--image" && !takeValue(argc, argv, i, options.image)) {
            throw dxapp::PipelineError("--image needs a path");
        } else if (arg == "--models-dir" && !takeValue(argc, argv, i, options.modelsDir)) {
            throw dxapp::PipelineError("--models-dir needs a path");
        } else if (arg == "--save" && !takeValue(argc, argv, i, options.savePath)) {
            throw dxapp::PipelineError("--save needs a path");
        } else if (arg != "--pipeline" && arg != "--image" && arg != "--models-dir" && arg != "--save" &&
                   arg != "--help" && arg != "-h") {
            throw dxapp::PipelineError("unknown argument: " + arg);
        }
    }
    return options;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parseArgs(argc, argv);
        if (options.help || options.pipeline.empty() || options.image.empty()) {
            printUsage();
            return options.help ? 0 : 1;
        }
        const cv::Mat frame = cv::imread(options.image, cv::IMREAD_COLOR);
        if (frame.empty()) {
            std::cerr << "[DXAPP] [ERROR] cannot read image: " << options.image << std::endl;
            return 1;
        }
        dxapp::MultiModelRunner runner(options.pipeline, options.modelsDir);
        const std::string fused = runner.runFrame(frame);
        std::cout << "[DXAPP] [INFO] pipeline=" << runner.pipeline().name << std::endl;
        std::cout << fused << std::endl;
        if (!options.savePath.empty()) {
            if (!cv::imwrite(options.savePath, frame)) {
                std::cerr << "[DXAPP] [ERROR] cannot write " << options.savePath << std::endl;
                return 1;
            }
            std::cout << "[DXAPP] [INFO] saved " << options.savePath << std::endl;
        }
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << "[DXAPP] [ERROR] " << exc.what() << std::endl;
        return 1;
    }
}

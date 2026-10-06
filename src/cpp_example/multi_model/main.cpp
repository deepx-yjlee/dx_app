/**
 * @file main.cpp
 * @brief Run one pipeline JSON file on one image or one video.
 *
 *   multi_model_run --pipeline <pipeline.json> (--image <frame> | --video <file>)
 *                    [--frames N] [--models-dir DIR] [--save PATH]
 */

#include "multi_model/runner.hpp"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/videoio.hpp>

#include <iostream>
#include <string>

namespace {

const double kMinWriterFps = 1.0;
const double kMaxWriterFps = 240.0;
const double kDefaultWriterFps = 30.0;

struct Options {
    std::string pipeline;
    std::string image;
    std::string video;
    std::string modelsDir;
    std::string savePath;
    std::size_t frames;  // 0 = every frame of --video
    bool help;
    Options() : frames(0), help(false) {}
};

void printUsage() {
    std::cout
        << "Usage: multi_model_run --pipeline <pipeline.json>\n"
        << "         (--image <frame> | --video <file>) [--frames N]\n"
        << "         [--models-dir DIR] [--save PATH]\n"
        << "\n"
        << "  --image and --video are mutually exclusive. --frames stops a\n"
        << "  video after N frames (default: all). --save with --video writes\n"
        << "  a .mp4, .avi, .mkv or .mov of the frames that ran.\n"
        << "\n"
        << "Pipelines:\n"
        << "  src/cpp_example/multi_model/hand_cascade/pipeline.json\n"
        << "  src/cpp_example/multi_model/logistics_volume/pipeline.json\n"
        << "  src/cpp_example/multi_model/dms_clip/pipeline.json\n";
}

std::size_t parseFrameLimit(const std::string& text);

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
        } else if (arg == "--video" && !takeValue(argc, argv, i, options.video)) {
            throw dxapp::PipelineError("--video needs a path");
        } else if (arg == "--frames") {
            std::string text;
            if (!takeValue(argc, argv, i, text)) {
                throw dxapp::PipelineError("--frames needs a positive integer");
            }
            options.frames = parseFrameLimit(text);
        } else if (arg == "--models-dir" && !takeValue(argc, argv, i, options.modelsDir)) {
            throw dxapp::PipelineError("--models-dir needs a path");
        } else if (arg == "--save" && !takeValue(argc, argv, i, options.savePath)) {
            throw dxapp::PipelineError("--save needs a path");
        } else if (arg != "--pipeline" && arg != "--image" && arg != "--video" && arg != "--frames" &&
                   arg != "--models-dir" && arg != "--save" && arg != "--help" && arg != "-h") {
            throw dxapp::PipelineError("unknown argument: " + arg);
        }
    }
    return options;
}

std::size_t parseFrameLimit(const std::string& text) {
    if (text.empty()) {
        throw dxapp::PipelineError("--frames needs a positive integer");
    }
    std::size_t value = 0;
    for (std::string::size_type i = 0; i < text.size(); ++i) {
        const char digit = text[i];
        if (digit < '0' || digit > '9') {
            throw dxapp::PipelineError("--frames needs a positive integer");
        }
        const std::size_t next = value * 10u + static_cast<std::size_t>(digit - '0');
        if (next < value) {
            throw dxapp::PipelineError("--frames is too large");
        }
        value = next;
    }
    if (value == 0) {
        throw dxapp::PipelineError("--frames must be at least 1");
    }
    return value;
}

std::string lowerExtension(const std::string& path) {
    const std::string::size_type dot = path.find_last_of('.');
    if (dot == std::string::npos) {
        return std::string();
    }
    std::string extension = path.substr(dot);
    for (std::string::size_type i = 0; i < extension.size(); ++i) {
        if (extension[i] >= 'A' && extension[i] <= 'Z') {
            extension[i] = static_cast<char>(extension[i] - 'A' + 'a');
        }
    }
    return extension;
}

bool isVideoSavePath(const std::string& path) {
    const std::string extension = lowerExtension(path);
    return extension == ".mp4" || extension == ".avi" || extension == ".mkv" || extension == ".mov";
}

double writerFps(double reported) {
    if (!(reported >= kMinWriterFps) || reported > kMaxWriterFps) {
        return kDefaultWriterFps;
    }
    return reported;
}

int videoFourcc(const std::string& path) {
    if (lowerExtension(path) == ".avi") {
        return cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
    }
    return cv::VideoWriter::fourcc('m', 'p', '4', 'v');
}

int runImage(const Options& options) {
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
}

int runVideo(const Options& options) {
    if (!options.savePath.empty() && !isVideoSavePath(options.savePath)) {
        throw dxapp::PipelineError("--save with --video needs a .mp4, .avi, .mkv or .mov path");
    }
    cv::VideoCapture capture(options.video);
    if (!capture.isOpened()) {
        std::cerr << "[DXAPP] [ERROR] cannot read video: " << options.video << std::endl;
        return 1;
    }
    dxapp::MultiModelRunner runner(options.pipeline, options.modelsDir);
    const double fps = writerFps(capture.get(cv::CAP_PROP_FPS));
    cv::VideoWriter writer;
    std::cout << "[DXAPP] [INFO] pipeline=" << runner.pipeline().name << std::endl;
    std::size_t index = 0;
    cv::Mat frame;
    while (capture.read(frame)) {
        if (frame.empty()) {
            break;
        }
        if (!options.savePath.empty() && !writer.isOpened()) {
            writer.open(options.savePath, videoFourcc(options.savePath), fps, frame.size());
            if (!writer.isOpened()) {
                std::cerr << "[DXAPP] [ERROR] cannot write " << options.savePath << std::endl;
                return 1;
            }
        }
        const std::string fused = runner.runFrame(frame);
        std::cout << "frame " << index << ": " << fused << std::endl;
        if (writer.isOpened()) {
            writer.write(frame);
        }
        ++index;
        if (options.frames != 0 && index >= options.frames) {
            break;
        }
    }
    writer.release();
    if (index == 0) {
        std::cerr << "[DXAPP] [ERROR] cannot read video: " << options.video << std::endl;
        return 1;
    }
    std::cout << "[DXAPP] [INFO] " << index << (index == 1 ? " frame" : " frames") << std::endl;
    if (!options.savePath.empty()) {
        std::cout << "[DXAPP] [INFO] saved " << options.savePath << std::endl;
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parseArgs(argc, argv);
        const bool missingInput = options.image.empty() && options.video.empty();
        if (options.help || options.pipeline.empty() || missingInput) {
            printUsage();
            return options.help ? 0 : 1;
        }
        if (!options.image.empty() && !options.video.empty()) {
            throw dxapp::PipelineError("pass either --image or --video");
        }
        if (options.frames != 0 && options.video.empty()) {
            throw dxapp::PipelineError("--frames applies to --video");
        }
        if (!options.video.empty()) {
            return runVideo(options);
        }
        return runImage(options);
    } catch (const std::exception& exc) {
        std::cerr << "[DXAPP] [ERROR] " << exc.what() << std::endl;
        return 1;
    }
}

/**
 * @file runner.cpp
 * @brief Wave execution, ROI binds, CPU head pose, and the four demo fusers.
 */

#include "multi_model/runner.hpp"
#include "multi_model/registry.hpp"

#include "common/utility/common_util.hpp"

#include <opencv2/calib3d.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <sstream>

namespace dxapp {
namespace {

const double kFaceRoiPadRatio = 0.15;
const int kPersonClassId = 0;
const double kDefaultScaleFactor = 1.0;
const double kSingularSy = 1e-6;

std::string parentPath(const std::string& path) {
    const std::string::size_type slash = path.find_last_of('/');
    if (slash == std::string::npos) {
        return "";
    }
    if (slash == 0) {
        return "/";
    }
    return path.substr(0, slash);
}

std::string joinPath(const std::string& left, const std::string& right) {
    if (left.empty()) {
        return right;
    }
    if (left[left.size() - 1] == '/') {
        return left + right;
    }
    return left + "/" + right;
}

std::string baseName(const std::string& path) {
    const std::string::size_type slash = path.find_last_of('/');
    if (slash == std::string::npos) {
        return path;
    }
    return path.substr(slash + 1);
}

std::string resolveModelFile(
    const std::string& filename,
    const std::string& pipelinePath,
    const std::string& modelsDir) {
    if (!filename.empty() && filename[0] == '/' && fileExists(filename)) {
        return filename;
    }
    std::vector<std::string> candidates;
    if (!modelsDir.empty()) {
        candidates.push_back(joinPath(modelsDir, filename));
    }
    const fs::path pipelineFile = fs::absolute(fs::path(pipelinePath));
    const std::string pipelineDir = pipelineFile.parent_path().string();
    if (!pipelineDir.empty()) {
        candidates.push_back(joinPath(joinPath(pipelineDir, "models"), filename));
        candidates.push_back(joinPath(pipelineDir, filename));
    }
    std::string cursor = pipelineDir.empty() ? std::string(".") : pipelineDir;
    while (!cursor.empty()) {
        candidates.push_back(joinPath(joinPath(joinPath(cursor, "workspace"), "res"), "models") +
                             "/" + filename);
        if (baseName(cursor) == "dx-all-suite") {
            break;
        }
        const std::string next = parentPath(cursor);
        if (next == cursor) {
            break;
        }
        cursor = next;
    }
    for (std::size_t i = 0; i < candidates.size(); ++i) {
        if (fileExists(candidates[i])) {
            return candidates[i];
        }
    }
    std::ostringstream searched;
    for (std::size_t i = 0; i < candidates.size(); ++i) {
        searched << "\n  " << candidates[i];
    }
    throw PipelineError("model '" + filename + "' was not found. Searched:" + searched.str());
}

double boxArea(const std::vector<float>& box) {
    if (box.size() < 4) {
        return 0.0;
    }
    const double width = std::max(0.0, static_cast<double>(box[2]) - static_cast<double>(box[0]));
    const double height = std::max(0.0, static_cast<double>(box[3]) - static_cast<double>(box[1]));
    return width * height;
}

float boxIou(const std::vector<float>& left, const std::vector<float>& right) {
    if (left.size() < 4 || right.size() < 4) {
        return 0.0f;
    }
    const float x1 = std::max(left[0], right[0]);
    const float y1 = std::max(left[1], right[1]);
    const float x2 = std::min(left[2], right[2]);
    const float y2 = std::min(left[3], right[3]);
    const float inter = std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);
    if (inter == 0.0f) {
        return 0.0f;
    }
    const float areaLeft = std::max(0.0f, left[2] - left[0]) * std::max(0.0f, left[3] - left[1]);
    const float areaRight = std::max(0.0f, right[2] - right[0]) * std::max(0.0f, right[3] - right[1]);
    const float unionArea = areaLeft + areaRight - inter;
    return unionArea > 0.0f ? inter / unionArea : 0.0f;
}

std::string lowerCopy(const std::string& text) {
    std::string lowered = text;
    for (std::size_t i = 0; i < lowered.size(); ++i) {
        lowered[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(lowered[i])));
    }
    return lowered;
}

bool isPackage(const BoxRecord& record) {
    if (record.classId == 24 || record.classId == 26 || record.classId == 28) {
        return true;
    }
    const std::string name = lowerCopy(record.className);
    return name == "backpack" || name == "handbag" || name == "suitcase" ||
           name == "box" || name == "package" || name == "luggage";
}

bool isPerson(const BoxRecord& record) {
    return record.classId == kPersonClassId || lowerCopy(record.className) == "person";
}

struct Crop {
    std::vector<float> box;
    cv::Mat image;
};

std::vector<Crop> cropBoxes(const cv::Mat& frame, const std::vector<BoxRecord>& records, double padRatio) {
    std::vector<Crop> crops;
    const int frameWidth = frame.cols;
    const int frameHeight = frame.rows;
    for (std::size_t i = 0; i < records.size(); ++i) {
        const std::vector<float>& raw = records[i].box;
        if (raw.size() < 4) {
            continue;
        }
        const int x1 = static_cast<int>(raw[0]);
        const int y1 = static_cast<int>(raw[1]);
        const int x2 = static_cast<int>(raw[2]);
        const int y2 = static_cast<int>(raw[3]);
        if (x2 <= x1 || y2 <= y1) {
            continue;
        }
        const int padX = static_cast<int>((x2 - x1) * padRatio);
        const int padY = static_cast<int>((y2 - y1) * padRatio);
        const int left = std::max(0, x1 - padX);
        const int top = std::max(0, y1 - padY);
        const int right = std::min(frameWidth, x2 + padX);
        const int bottom = std::min(frameHeight, y2 + padY);
        if (right <= left || bottom <= top) {
            continue;
        }
        Crop crop;
        crop.box.push_back(static_cast<float>(left));
        crop.box.push_back(static_cast<float>(top));
        crop.box.push_back(static_cast<float>(right));
        crop.box.push_back(static_cast<float>(bottom));
        crop.image = frame(cv::Rect(left, top, right - left, bottom - top)).clone();
        crops.push_back(crop);
    }
    return crops;
}

const BoxRecord* largestBox(const std::vector<BoxRecord>& records) {
    const BoxRecord* best = nullptr;
    double bestArea = -1.0;
    for (std::size_t i = 0; i < records.size(); ++i) {
        const double area = boxArea(records[i].box);
        if (records[i].box.size() >= 4 && area > bestArea) {
            best = &records[i];
            bestArea = area;
        }
    }
    return best;
}

struct StageBundle {
    bool bound;
    std::vector<StageCall> calls;

    StageBundle() : bound(false) {}
};

const StageOutput* directOutput(const StageBundle& bundle) {
    if (bundle.bound || bundle.calls.empty()) {
        return nullptr;
    }
    return &bundle.calls.front().output;
}

const std::vector<BoxRecord>& boxesOf(const StageBundle& bundle) {
    static const std::vector<BoxRecord> kEmpty;
    const StageOutput* output = directOutput(bundle);
    return output == nullptr ? kEmpty : output->boxes;
}

std::vector<StageCall> runBound(
    IStage& stage,
    const cv::Mat& frame,
    const StageBundle& upstream,
    const std::string& op) {
    std::vector<BoxRecord> selected = boxesOf(upstream);
    double padRatio = 0.0;
    if (op == "face_roi") {
        const BoxRecord* face = largestBox(selected);
        BoxRecord chosen;
        const bool found = face != nullptr;
        if (found) {
            chosen = *face;
        }
        selected.clear();
        if (found) {
            selected.push_back(chosen);
        }
        padRatio = kFaceRoiPadRatio;
    } else if (op != "roi") {
        throw PipelineError("unknown bind op '" + op + "'");
    }
    const std::vector<Crop> crops = cropBoxes(frame, selected, padRatio);
    std::vector<StageCall> calls;
    for (std::size_t i = 0; i < crops.size(); ++i) {
        StageCall call;
        call.inputBox = crops[i].box;
        call.output = stage.run(crops[i].image);
        calls.push_back(call);
    }
    return calls;
}

StageOutput faceSolvePnp(const cv::Mat& frame, const StageBundle& faces) {
    StageOutput output;
    const BoxRecord* face = largestBox(boxesOf(faces));
    if (face == nullptr || face->keypoints.size() < 5) {
        return output;
    }
    // FaceDetectionResult order: left eye, right eye, nose, left mouth, right mouth.
    const float kModel[5][3] = {
        {-30.0f, -30.0f, -30.0f},
        {30.0f, -30.0f, -30.0f},
        {0.0f, 0.0f, 0.0f},
        {-25.0f, 30.0f, -20.0f},
        {25.0f, 30.0f, -20.0f},
    };
    std::vector<cv::Point3d> objectPoints;
    std::vector<cv::Point2d> imagePoints;
    for (int i = 0; i < 5; ++i) {
        objectPoints.push_back(cv::Point3d(kModel[i][0], kModel[i][1], kModel[i][2]));
        imagePoints.push_back(cv::Point2d(face->keypoints[i].x, face->keypoints[i].y));
    }
    const double focal = static_cast<double>(frame.cols);
    const cv::Mat camera = (cv::Mat_<double>(3, 3) <<
        focal, 0.0, focal / 2.0,
        0.0, focal, static_cast<double>(frame.rows) / 2.0,
        0.0, 0.0, 1.0);
    cv::Mat rotation;
    cv::Mat translation;
    const bool solved = cv::solvePnP(
        objectPoints, imagePoints, camera, cv::Mat::zeros(4, 1, CV_64F),
        rotation, translation, false, cv::SOLVEPNP_SQPNP);
    if (!solved) {
        return output;
    }
    cv::Mat matrix;
    cv::Rodrigues(rotation, matrix);
    const double sy = std::sqrt(
        matrix.at<double>(0, 0) * matrix.at<double>(0, 0) +
        matrix.at<double>(1, 0) * matrix.at<double>(1, 0));
    double pitch = 0.0;
    double yaw = 0.0;
    double roll = 0.0;
    if (sy < kSingularSy) {
        pitch = std::atan2(-matrix.at<double>(1, 2), matrix.at<double>(1, 1));
        yaw = std::atan2(-matrix.at<double>(2, 0), sy);
        roll = 0.0;
    } else {
        pitch = std::atan2(matrix.at<double>(2, 1), matrix.at<double>(2, 2));
        yaw = std::atan2(-matrix.at<double>(2, 0), sy);
        roll = std::atan2(matrix.at<double>(1, 0), matrix.at<double>(0, 0));
    }
    const double kRadToDeg = 180.0 / 3.14159265358979323846;
    output.hasHeadPose = true;
    output.pitchDeg = pitch * kRadToDeg;
    output.yawDeg = yaw * kRadToDeg;
    output.rollDeg = roll * kRadToDeg;
    return output;
}

StageBundle runCpu(const StageSpec& spec, const cv::Mat& frame, const std::map<std::string, StageBundle>& outputs) {
    if (spec.op != "face_solvepnp") {
        throw PipelineError("stage '" + spec.id + "' has unknown cpu op '" + spec.op + "'");
    }
    std::map<std::string, StageBundle>::const_iterator face = outputs.find("face");
    StageBundle bundle;
    StageCall call;
    if (face == outputs.end()) {
        call.output = StageOutput();
    } else {
        call.output = faceSolvePnp(frame, face->second);
    }
    bundle.calls.push_back(call);
    return bundle;
}

int countOnMask(const cv::Mat& mask) {
    if (mask.empty()) {
        return 0;
    }
    cv::Mat plane;
    if (mask.channels() == 1) {
        plane = mask;
    } else {
        cv::extractChannel(mask, plane, 0);
    }
    int count = 0;
    for (int y = 0; y < plane.rows; ++y) {
        for (int x = 0; x < plane.cols; ++x) {
            bool on = false;
            if (plane.depth() == CV_8U) {
                on = plane.at<unsigned char>(y, x) > 0;
            } else if (plane.depth() == CV_32F) {
                on = plane.at<float>(y, x) > 0.0f;
            } else if (plane.depth() == CV_64F) {
                on = plane.at<double>(y, x) > 0.0;
            }
            if (on) {
                ++count;
            }
        }
    }
    return count;
}

bool medianUnderMask(const cv::Mat& depth, const cv::Mat& mask, double& median) {
    if (depth.empty() || mask.empty() || depth.rows != mask.rows || depth.cols != mask.cols) {
        return false;
    }
    if (depth.channels() != 1) {
        return false;
    }
    cv::Mat plane;
    if (mask.channels() == 1) {
        plane = mask;
    } else {
        cv::extractChannel(mask, plane, 0);
    }
    if (plane.rows != depth.rows || plane.cols != depth.cols) {
        return false;
    }
    std::vector<double> samples;
    for (int y = 0; y < depth.rows; ++y) {
        for (int x = 0; x < depth.cols; ++x) {
            bool on = false;
            if (plane.depth() == CV_8U) {
                on = plane.at<unsigned char>(y, x) > 0;
            } else if (plane.depth() == CV_32F) {
                on = plane.at<float>(y, x) > 0.0f;
            } else if (plane.depth() == CV_64F) {
                on = plane.at<double>(y, x) > 0.0;
            }
            if (!on) {
                continue;
            }
            double value = 0.0;
            if (depth.depth() == CV_32F) {
                value = depth.at<float>(y, x);
            } else if (depth.depth() == CV_64F) {
                value = depth.at<double>(y, x);
            } else {
                return false;
            }
            if (std::isfinite(value)) {
                samples.push_back(value);
            }
        }
    }
    if (samples.empty()) {
        return false;
    }
    const std::size_t mid = samples.size() / 2;
    std::nth_element(samples.begin(), samples.begin() + static_cast<std::ptrdiff_t>(mid), samples.end());
    if (samples.size() % 2 == 1) {
        median = samples[mid];
        return true;
    }
    const double upper = samples[mid];
    std::nth_element(samples.begin(), samples.begin() + static_cast<std::ptrdiff_t>(mid - 1), samples.end());
    median = (samples[mid - 1] + upper) / 2.0;
    return true;
}

const BoxRecord* bestOverlap(const BoxRecord& detection, const std::vector<BoxRecord>& segments) {
    const BoxRecord* best = nullptr;
    float bestIou = 0.0f;
    for (std::size_t i = 0; i < segments.size(); ++i) {
        const float iou = boxIou(detection.box, segments[i].box);
        if (iou > bestIou) {
            best = &segments[i];
            bestIou = iou;
        }
    }
    return best;
}

std::string fuseHand(const std::map<std::string, StageBundle>& outputs) {
    const std::map<std::string, StageBundle>::const_iterator palm = outputs.find("palm");
    const std::map<std::string, StageBundle>::const_iterator landmark = outputs.find("landmark");
    int palms = 0;
    if (palm != outputs.end()) {
        const std::vector<BoxRecord>& boxes = boxesOf(palm->second);
        for (std::size_t i = 0; i < boxes.size(); ++i) {
            if (boxArea(boxes[i].box) > 0.0) {
                ++palms;
            }
        }
    }
    const int hands = landmark == outputs.end() ? 0 : static_cast<int>(landmark->second.calls.size());
    std::ostringstream text;
    text << "event=" << (hands > 0 ? "HANDS" : "NO_HAND")
         << " palms=" << palms << " hands=" << hands;
    return text.str();
}

std::string fuseLogistics(
    const std::map<std::string, StageBundle>& outputs,
    const std::map<std::string, double>& config) {
    std::vector<BoxRecord> packages;
    std::vector<BoxRecord> segments;
    std::map<std::string, StageBundle>::const_iterator det = outputs.find("det");
    if (det != outputs.end()) {
        const std::vector<BoxRecord>& boxes = boxesOf(det->second);
        for (std::size_t i = 0; i < boxes.size(); ++i) {
            if (isPackage(boxes[i])) {
                packages.push_back(boxes[i]);
            }
        }
    }
    std::map<std::string, StageBundle>::const_iterator seg = outputs.find("seg");
    if (seg != outputs.end()) {
        const std::vector<BoxRecord>& boxes = boxesOf(seg->second);
        for (std::size_t i = 0; i < boxes.size(); ++i) {
            if (isPackage(boxes[i])) {
                segments.push_back(boxes[i]);
            }
        }
    }
    cv::Mat depthMap;
    std::map<std::string, StageBundle>::const_iterator depth = outputs.find("depth");
    if (depth != outputs.end()) {
        const StageOutput* output = directOutput(depth->second);
        if (output != nullptr) {
            depthMap = output->depthMap;
        }
    }
    std::map<std::string, double>::const_iterator scaleIt = config.find("scale_factor");
    const double scale = scaleIt == config.end() ? kDefaultScaleFactor : scaleIt->second;
    std::ostringstream text;
    text << "event=" << (packages.empty() ? "NO_BOX" : "BOX_MEASURED")
         << " packages=" << packages.size();
    for (std::size_t i = 0; i < packages.size(); ++i) {
        const BoxRecord* segment = bestOverlap(packages[i], segments);
        const int area = segment == nullptr ? 0 : countOnMask(segment->mask);
        double median = 0.0;
        const bool hasMedian = segment != nullptr && medianUnderMask(depthMap, segment->mask, median);
        text << "\n  box=";
        if (packages[i].box.size() >= 4) {
            text << packages[i].box[0] << "," << packages[i].box[1] << ","
                 << packages[i].box[2] << "," << packages[i].box[3];
        }
        text << " mask_area_px=" << area << " median_depth=";
        if (hasMedian && area > 0) {
            text << median << " volume_proxy=" << (area * median * scale);
        } else {
            text << "none volume_proxy=none";
        }
    }
    return text.str();
}

std::string fuseSafety(const std::map<std::string, StageBundle>& outputs) {
    int persons = 0;
    int ppe = 0;
    int poses = 0;
    std::map<std::string, StageBundle>::const_iterator person = outputs.find("person");
    if (person != outputs.end()) {
        const std::vector<BoxRecord>& boxes = boxesOf(person->second);
        for (std::size_t i = 0; i < boxes.size(); ++i) {
            if (isPerson(boxes[i])) {
                ++persons;
            }
        }
    }
    std::map<std::string, StageBundle>::const_iterator ppeIt = outputs.find("ppe");
    if (ppeIt != outputs.end()) {
        ppe = static_cast<int>(boxesOf(ppeIt->second).size());
    }
    std::map<std::string, StageBundle>::const_iterator pose = outputs.find("pose");
    if (pose != outputs.end()) {
        poses = static_cast<int>(boxesOf(pose->second).size());
    }
    std::ostringstream text;
    text << "event=" << (persons > 0 ? "PERSONS" : "NO_PERSON")
         << " persons=" << persons << " ppe=" << ppe << " poses=" << poses;
    return text.str();
}

std::string fuseDms(const std::map<std::string, StageBundle>& outputs) {
    int faces = 0;
    int poses = 0;
    int clipRois = 0;
    std::map<std::string, StageBundle>::const_iterator face = outputs.find("face");
    if (face != outputs.end()) {
        const std::vector<BoxRecord>& boxes = boxesOf(face->second);
        for (std::size_t i = 0; i < boxes.size(); ++i) {
            if (boxArea(boxes[i].box) > 0.0) {
                ++faces;
            }
        }
    }
    std::map<std::string, StageBundle>::const_iterator pose = outputs.find("pose");
    if (pose != outputs.end()) {
        poses = static_cast<int>(boxesOf(pose->second).size());
    }
    std::map<std::string, StageBundle>::const_iterator clip = outputs.find("clip");
    if (clip != outputs.end()) {
        clipRois = static_cast<int>(clip->second.calls.size());
    }
    std::ostringstream text;
    text << "event=" << (faces > 0 ? "DRIVER" : "NO_DRIVER")
         << " faces=" << faces << " poses=" << poses << " clip_rois=" << clipRois
         << " headpose=";
    std::map<std::string, StageBundle>::const_iterator head = outputs.find("headpose");
    if (head == outputs.end() || head->second.calls.empty() || !head->second.calls.front().output.hasHeadPose) {
        text << "none";
    } else {
        const StageOutput& poseOut = head->second.calls.front().output;
        text << "pitch=" << poseOut.pitchDeg << ",yaw=" << poseOut.yawDeg << ",roll=" << poseOut.rollDeg;
    }
    return text.str();
}

std::string fuseOutputs(
    const std::string& name,
    const std::map<std::string, StageBundle>& outputs,
    const std::map<std::string, double>& config) {
    if (name == "hand_cascade") {
        return fuseHand(outputs);
    }
    if (name == "logistics_volume") {
        return fuseLogistics(outputs, config);
    }
    if (name == "worker_safety") {
        return fuseSafety(outputs);
    }
    if (name == "dms") {
        return fuseDms(outputs);
    }
    throw PipelineError("unknown fuse '" + name + "'");
}

}  // namespace

MultiModelRunner::MultiModelRunner(const std::string& pipelinePath, const std::string& modelsDir)
    : pipeline_(loadPipeline(pipelinePath)) {
    for (std::size_t i = 0; i < pipeline_.stages.size(); ++i) {
        const StageSpec& spec = pipeline_.stages[i];
        if (spec.kind != "npu") {
            continue;
        }
        const std::string modelPath = resolveModelFile(spec.model, pipelinePath, modelsDir);
        stages_[spec.id] = createRegisteredStage(spec.task, spec.family, spec.variant, spec.id, modelPath);
        std::cout << "[DXAPP] [INFO] stage ready: " << spec.id
                  << " variant=" << spec.variant
                  << " model=" << modelPath << std::endl;
    }
}

std::string MultiModelRunner::runFrame(const cv::Mat& frame) {
    if (frame.empty()) {
        throw PipelineError("empty frame");
    }
    std::map<std::string, StageBundle> outputs;
    const std::vector<std::vector<StageSpec>> waves = executionWaves(pipeline_.stages);
    for (std::size_t waveIndex = 0; waveIndex < waves.size(); ++waveIndex) {
        for (std::size_t stageIndex = 0; stageIndex < waves[waveIndex].size(); ++stageIndex) {
            const StageSpec& spec = waves[waveIndex][stageIndex];
            StageBundle bundle;
            if (spec.kind == "cpu") {
                bundle = runCpu(spec, frame, outputs);
            } else {
                std::map<std::string, std::unique_ptr<IStage>>::iterator engine = stages_.find(spec.id);
                if (engine == stages_.end()) {
                    throw PipelineError("stage '" + spec.id + "' has no engine");
                }
                if (!spec.hasBind) {
                    StageCall call;
                    call.output = engine->second->run(frame);
                    bundle.calls.push_back(call);
                } else {
                    std::map<std::string, StageBundle>::const_iterator upstream = outputs.find(spec.bind.source);
                    StageBundle empty;
                    const StageBundle& source = upstream == outputs.end() ? empty : upstream->second;
                    bundle.bound = true;
                    bundle.calls = runBound(*engine->second, frame, source, spec.bind.op);
                }
            }
            outputs[spec.id] = bundle;
        }
    }
    return fuseOutputs(pipeline_.fuse, outputs, pipeline_.fuseConfig);
}

}  // namespace dxapp

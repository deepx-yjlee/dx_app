/**
 * @file efficientad_factory.hpp
 * @brief EfficientAD-M factory
 *
 * Hand-written, not carried over from a donor: no existing family in this tree
 * consumes this model's output.
 *
 * EfficientAD ships as THREE .dxnn files and its map is the combination of two
 * disagreements, so this factory declares the other two as companions and the anomaly
 * runner resolves them beside whichever one -m named. The roles are declared with
 * them, because teacher and autoencoder are both (1,384,H,W) and the arrival order is
 * the only thing that distinguishes them -- and the primary is whichever file -m
 * names, so that order changes per variant.
 */

#ifndef EFFICIENTAD_FACTORY_HPP
#define EFFICIENTAD_FACTORY_HPP

#include "common/base/i_factory.hpp"
#include "common/processors/simple_resize_preprocessor.hpp"
#include "common/processors/efficientad_postprocessor.hpp"
#include "common/visualizers/anomaly_visualizer.hpp"
#include "common/config/model_config.hpp"
#include "common/utility/common_util.hpp"

#include <array>
#include <string>
#include <utility>
#include <vector>

namespace dxapp {

class EfficientadFactory : public IAnomalyDetectionFactory {
public:
    /// Select the variant (a .dxnn stem) this factory builds for.
    /// Empty means the family default. Called from main(), the
    /// only place that sees argv.
    void setVariant(std::string variant) { variant_ = std::move(variant); }

    EfficientadFactory() = default;

    PreprocessorPtr createPreprocessor(int input_width, int input_height) override {
        return std::make_unique<SimpleResizePreprocessor>(input_width, input_height);
    }

    PostprocessorPtr<AnomalyResult> createPostprocessor(
        int input_width, int input_height) override {
        return std::make_unique<EfficientADPostprocessor>(
            input_width, input_height, outputRoles());
    }

    VisualizerPtr<AnomalyResult> createVisualizer() override {
        return std::make_unique<AnomalyVisualizer>();
    }

    /**
     * @brief The other two networks, beside the one -m named.
     *
     * EfficientAD scores a DISAGREEMENT -- the student's first 384 channels predict
     * the teacher and its second 384 predict the autoencoder -- so no single network
     * can produce the map. Declaring the set here keeps the one--m CLI contract that
     * run_demo.sh and every sweep rely on; the runner resolves these names in the
     * primary model's own directory.
     */
    std::vector<std::pair<std::string, std::string>> getCompanionModels(
        const std::string& primary_path) const override {
        const std::string primary = primaryRole(primary_path);
        std::vector<std::pair<std::string, std::string>> companions;
        const std::string stem = fs::path(primary_path).filename().string();
        for (const char* role : roles()) {
            if (primary == role) continue;
            std::string name = stem;
            const std::string from = "-" + primary + "_";
            const std::string to = std::string("-") + role + "_";
            const auto at = name.find(from);
            if (at == std::string::npos) continue;
            name.replace(at, from.size(), to);
            companions.emplace_back(role, name);
        }
        return companions;
    }

    std::string getModelName() const override {
        // The variant IS the .dxnn stem, so it names the model actually loaded --
        // every runner builds its artifact directory and window title from this.
        // The literal is the family fallback for a bare run with no -m.
        return variant_.empty() ? "EfficientAD-M" : variant_;
    }
    std::string getTaskType() const override { return "anomaly_detection"; }

private:
    /// The three networks, in the canonical order. A function-local static rather
    /// than a `static constexpr` member: this tree is C++14, where such a member still
    /// needs an out-of-line definition and the link fails without one.
    static const std::array<const char*, 3>& roles() {
        static const std::array<const char*, 3> kRoles{
            {"student", "teacher", "autoencoder"}};
        return kRoles;
    }

    /// Which network -m named. The .dxnn stem carries it: efficientad-m-<role>_256x256.
    static std::string primaryRole(const std::string& path) {
        const std::string stem = fs::path(path).filename().string();
        for (const char* role : roles()) {
            if (stem.find(std::string("-") + role + "_") != std::string::npos) {
                return role;
            }
        }
        return "student";
    }

    /**
     * @brief Output roles in ARRIVAL order: the primary first, then the companions.
     *
     * Must match getCompanionModels() exactly -- that is the whole contract by which
     * the postprocessor tells two identically-shaped 384-channel maps apart.
     */
    std::vector<std::string> outputRoles() const {
        const std::string primary =
            variant_.empty() ? std::string("student") : primaryRole(variant_);
        std::vector<std::string> ordered{primary};
        for (const char* role : roles()) {
            if (primary != role) ordered.emplace_back(role);
        }
        return ordered;
    }

    std::string variant_;
};

}  // namespace dxapp

#endif  // EFFICIENTAD_FACTORY_HPP

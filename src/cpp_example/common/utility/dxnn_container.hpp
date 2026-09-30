/**
 * @file dxnn_container.hpp
 * @brief The container version of a .dxnn file, read without the runtime.
 *
 * A .dxnn file starts with the four bytes "DXNN" and then the container
 * version as a little-endian uint32 (bytes 4-7). The model zoo's 2_4_0 files
 * are version 8 (a few older ones 6); its 2_5_0 files are version 9, which
 * DX-RT loads only from 3.5.0 on. Reading the version here, before any
 * engine is created, lets the graph paths say which file a user has
 * (--list-models) and refuse one this runtime cannot load with one clear
 * text (ContainerSupportError) instead of leaving it to the runtime's own
 * error.
 *
 * Known table: a container <= 8 loads on every DX-RT 3.x this repository
 * supports; 9 needs DX-RT >= 3.5.0; a newer one needs a DX-RT newer than
 * the running one. The runtime version is the caller's
 * (dxrt::Configuration::GetInstance().GetVersion()), so nothing here needs
 * the runtime.
 */
#ifndef DXAPP_UTILITY_DXNN_CONTAINER_HPP
#define DXAPP_UTILITY_DXNN_CONTAINER_HPP

#include <cctype>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

namespace dxapp {

/**
 * @brief Read the container version of the .dxnn file at `path`.
 *
 * True on success, with *version set. False when the file cannot be opened,
 * is shorter than the 8-byte header, or does not start with "DXNN"; then
 * *error says which and *version is left as it was.
 */
inline bool ReadDxnnContainerVersion(const std::string& path, uint32_t* version,
                                     std::string* error) {
    std::ifstream in(path.c_str(), std::ios::binary);
    if (!in.is_open()) {
        *error = path + ": cannot open the file";
        return false;
    }
    unsigned char header[8] = {0};
    in.read(reinterpret_cast<char*>(header), sizeof(header));
    if (in.gcount() != static_cast<std::streamsize>(sizeof(header))) {
        *error = path + ": too short for a .dxnn header (8 bytes)";
        return false;
    }
    if (std::memcmp(header, "DXNN", 4) != 0) {
        *error = path + ": not a .dxnn file (no DXNN magic)";
        return false;
    }
    *version = static_cast<uint32_t>(header[4]) | (static_cast<uint32_t>(header[5]) << 8) |
               (static_cast<uint32_t>(header[6]) << 16) | (static_cast<uint32_t>(header[7]) << 24);
    return true;
}

namespace detail {

/// "3.4.1", "v3.4.1+baec914", "3.5" -> {3, 4, 1}, {3, 4, 1}, {3, 5, 0}.
/// False for anything without at least <major>.<minor> in digits.
inline bool ParseRuntimeVersion(const std::string& text, int parts[3]) {
    std::size_t at = (!text.empty() && (text[0] == 'v' || text[0] == 'V')) ? 1 : 0;
    int count = 0;
    parts[0] = parts[1] = parts[2] = 0;
    while (count < 3) {
        if (at >= text.size() || !std::isdigit(static_cast<unsigned char>(text[at]))) break;
        int value = 0;
        while (at < text.size() && std::isdigit(static_cast<unsigned char>(text[at]))) {
            if (value > 9999) return false;
            value = value * 10 + (text[at] - '0');
            ++at;
        }
        parts[count++] = value;
        if (at >= text.size() || text[at] != '.') break;
        ++at;
    }
    return count >= 2;
}

inline std::string VersionText(const int parts[3]) {
    std::ostringstream out;
    out << parts[0] << "." << parts[1] << "." << parts[2];
    return out.str();
}

}  // namespace detail

/**
 * @brief Why DX-RT `runtime` cannot load a .dxnn container of `version`,
 *        in short ("needs DX-RT >= 3.5.0"); "" when it can.
 *
 * Also "" when `runtime` is not a version this can read: then nothing is
 * refused here, and the runtime's own loader decides.
 */
inline std::string ContainerRequirement(uint32_t version, const std::string& runtime) {
    int parts[3];
    if (version <= 8 || !detail::ParseRuntimeVersion(runtime, parts)) return std::string();
    if (version == 9) {
        const bool below_350 =
            parts[0] < 3 || (parts[0] == 3 && parts[1] < 5);
        return below_350 ? "needs DX-RT >= 3.5.0" : std::string();
    }
    return "needs a DX-RT newer than v" + detail::VersionText(parts);
}

/**
 * @brief The whole refusal for a container of `version` on DX-RT `runtime`
 *        (spec section 4), or "" when it loads there.
 *
 * v9 on 3.4.1: ".dxnn container v9 needs DX-RT >= 3.5.0, but this runtime
 * is 3.4.1. Use the v8 file (dxnn/2_4_0) or upgrade DX-RT."
 */
inline std::string ContainerSupportError(uint32_t version, const std::string& runtime) {
    const std::string requirement = ContainerRequirement(version, runtime);
    if (requirement.empty()) return std::string();
    int parts[3];
    detail::ParseRuntimeVersion(runtime, parts);
    const std::string container = ".dxnn container v" + std::to_string(version) + " ";
    if (version == 9) {
        return container + requirement + ", but this runtime is " + detail::VersionText(parts) +
               ". Use the v8 file (dxnn/2_4_0) or upgrade DX-RT.";
    }
    return container + requirement + " (this runtime). Upgrade DX-RT.";
}

/**
 * @brief "<path>: <ContainerSupportError>" for the .dxnn at `path`, or ""
 *        when it loads on DX-RT `runtime`.
 *
 * Also "" when the header cannot be read (absent, short, no magic): the
 * caller reports a missing file, and the runtime names a broken one.
 */
inline std::string ContainerLoadError(const std::string& path, const std::string& runtime) {
    uint32_t version = 0;
    std::string error;
    if (!ReadDxnnContainerVersion(path, &version, &error)) return std::string();
    const std::string support = ContainerSupportError(version, runtime);
    return support.empty() ? std::string() : path + ": " + support;
}

}  // namespace dxapp

#endif  // DXAPP_UTILITY_DXNN_CONTAINER_HPP

/**
 * @file dxnn_container.hpp
 * @brief The container version of a .dxnn file, read without the runtime.
 *
 * A .dxnn file starts with the four bytes "DXNN" and then the container
 * version as a little-endian uint32 (bytes 4-7). The model zoo's 2_4_0 files
 * are version 8 (a few older ones 6); its 2_5_0 files are version 9, which
 * DX-RT loads only from 3.5.0 on. Reading the version here, before any
 * engine is created, lets the graph paths say which file a user has
 * (--list-models) instead of leaving it to the runtime's own error.
 */
#ifndef DXAPP_UTILITY_DXNN_CONTAINER_HPP
#define DXAPP_UTILITY_DXNN_CONTAINER_HPP

#include <cstdint>
#include <cstring>
#include <fstream>
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

}  // namespace dxapp

#endif  // DXAPP_UTILITY_DXNN_CONTAINER_HPP

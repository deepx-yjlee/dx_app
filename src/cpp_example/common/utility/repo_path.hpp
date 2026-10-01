/**
 * @file repo_path.hpp
 * @brief One rule for a path that is relative to the repository.
 *
 * Sample inputs, galleries and the images a gallery names ship as
 * "sample/..." paths: relative to the repository (PROJECT_ROOT_DIR), not to
 * the caller's working directory. The graph CLI's --check, a graph stage's
 * config overlay and the retrieval visualizer all read such paths, and each
 * must find the file the others find, from any directory.
 *
 * An absolute path is kept as given; an empty one stays empty.
 */
#ifndef DXAPP_REPO_PATH_HPP
#define DXAPP_REPO_PATH_HPP

#include <string>

namespace dxapp {

/// "/a", "\\a" and "C:..." are absolute; "" and "sample/x" are not.
inline bool IsAbsolutePath(const std::string& path) {
    if (path.empty()) return false;
    if (path[0] == '/' || path[0] == '\\') return true;
    return path.size() > 1 && path[1] == ':';
}

/// `path` read against `root`: a relative path is joined, an absolute or
/// empty one is returned as given.
inline std::string ResolveAgainstRoot(const std::string& root, const std::string& path) {
    if (path.empty() || IsAbsolutePath(path)) return path;
    return root + "/" + path;
}

#if defined(PROJECT_ROOT_DIR)
/// `path` read against the repository this build was configured from.
inline std::string ResolveRepoRelative(const std::string& path) {
    return ResolveAgainstRoot(PROJECT_ROOT_DIR, path);
}
#endif

}  // namespace dxapp

#endif  // DXAPP_REPO_PATH_HPP

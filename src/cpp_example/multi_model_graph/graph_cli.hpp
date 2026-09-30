/**
 * @file graph_cli.hpp
 * @brief Everything both multi-model-graph binaries share.
 *
 * WHY THIS FILE IS NOT UNDER common/graph/
 * ----------------------------------------
 * This is the engine's CONSUMER, not the engine. It constructs a concrete
 * registry (common/registry/static_model_registry.hpp) and that is exactly
 * what scripts/check_graph_boundary.py exists to keep out of
 * common/graph/. The guard walks every file under that directory, so a
 * graph_cli.cpp placed there would either fail the guard or force
 * static_model_registry.hpp onto ENGINE_INCLUDE_ALLOWLIST, which would
 * open the allowlist to every engine file and defeat the guard entirely.
 * Living here, next to the two mains it serves, the CLI can name the
 * concrete registry the way it is meant to: once, at the top of main().
 *
 * The two binaries differ in exactly one value - which executor runs a
 * frame - so everything else lives in graph_cli.cpp and each main is six
 * lines.
 */
#ifndef DXAPP_MULTI_MODEL_GRAPH_GRAPH_CLI_HPP
#define DXAPP_MULTI_MODEL_GRAPH_GRAPH_CLI_HPP

namespace dxapp {
namespace graph {
namespace cli {

/// Which executor Main() constructs. The only difference between the two
/// shipped binaries.
enum ExecutorKind { kSyncExecutor, kAsyncExecutor };

/**
 * @brief Parse arguments, build the graph, run it. The whole program.
 *
 * Exit codes, which scripts depend on:
 *   0  success, or --help / --list-models / a --check whose graph is valid
 *   1  a GraphError: the graph, or the models it names, cannot run
 *   2  a usage error: an unknown option, a missing value, no graph
 */
int Main(int argc, char** argv, ExecutorKind kind);

}  // namespace cli
}  // namespace graph
}  // namespace dxapp

#endif  // DXAPP_MULTI_MODEL_GRAPH_GRAPH_CLI_HPP

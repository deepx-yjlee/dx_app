# =============================================================================
# cpp_example - DEEPX C++ Example Programs (Factory Pattern)
# =============================================================================
cmake_minimum_required(VERSION 3.14)
project(cpp_example DESCRIPTION "DEEPX C++ Example Programs")

if(NOT CMAKE_CXX_STANDARD)
    set(CMAKE_CXX_STANDARD 17)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

# =============================================================================
# Project Root Configuration
# =============================================================================
if(NOT PROJECT_ROOT)
    get_filename_component(PROJECT_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../.. ABSOLUTE)
endif()

set(CPP_EXAMPLE_DIR ${CMAKE_CURRENT_SOURCE_DIR})
set(COMMON_DIR ${CPP_EXAMPLE_DIR}/common)

# =============================================================================
# Find Required Packages
# =============================================================================
find_package(OpenCV REQUIRED HINTS ${OpenCV_DIR})
find_package(PkgConfig REQUIRED)

# Find dxrt library
if(MSVC)
    find_library(DXRT_LIB dxrt HINTS ${DXRT_INSTALLED_DIR}/lib/x64 REQUIRED)
    include_directories(${DXRT_INSTALLED_DIR}/include)
    link_directories(${DXRT_INSTALLED_DIR}/lib/x64)
elseif(CROSS_COMPILE)
    find_library(DXRT_LIB dxrt HINTS ${DXRT_INSTALLED_DIR}/lib)
    include_directories(${DXRT_INSTALLED_DIR}/include)
    link_directories(${DXRT_INSTALLED_DIR}/lib)
else()
    find_package(dxrt REQUIRED HINTS ${DXRT_INSTALLED_DIR})
    set(DXRT_LIB dxrt)
endif()

if(NOT DXRT_LIB)
    message(FATAL_ERROR "dxrt library not found. Please ensure it is installed and accessible.")
endif()

# =============================================================================
# Include Directories
# =============================================================================
include_directories(${OpenCV_INCLUDE_DIRS})
include_directories(${PROJECT_ROOT}/extern/)
include_directories(${PROJECT_ROOT}/src/utility/)
include_directories(${PROJECT_ROOT}/src/postprocess/sfa3d)
include_directories(${PROJECT_ROOT}/src/postprocess/superpoint)
include_directories(${CPP_EXAMPLE_DIR})  # For common/ includes

# Postprocess headers (header-only .hpp in common/processors/)
include_directories(${CPP_EXAMPLE_DIR}/common/processors)

# =============================================================================
# Common Libraries
# =============================================================================
set(COMMON_LIBS ${OpenCV_LIBS} ${DXRT_LIB})

# Platform-specific filesystem library linking for C++17
if(NOT STD_FS_NO_LIB_NEEDED)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        list(APPEND COMMON_LIBS stdc++fs)
    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
        list(APPEND COMMON_LIBS c++fs)
    endif()
endif()

# =============================================================================
# Common Compiler Flags and Definitions
# =============================================================================
if(MSVC)
    set(COMMON_COMPILE_FLAGS /W3 /MP)
else()
    set(COMMON_COMPILE_FLAGS -Wall -Wextra -O3)
endif()
set(COMMON_COMPILE_DEFINITIONS PROJECT_ROOT_DIR="${PROJECT_ROOT}")

# =============================================================================
# Runtime DLL Deployment — Windows/vcpkg only, stage once instead of per target
# =============================================================================
# Windows only. On Linux the loader resolves shared libraries through RPATH and
# ldconfig, there is no vcpkg in the picture (build.sh uses
# cmake/toolchain.<arch>.cmake), and nothing below runs.
if(WIN32)
    # vcpkg keys applocal off the target triplet rather than the compiler, so
    # guard on WIN32 rather than MSVC to also cover clang-cl / MinGW.
    set(VCPKG_APPLOCAL_DEPS OFF)

    if(DEFINED VCPKG_INSTALLED_DIR)
        set(_DXAPP_TRIPLET "${VCPKG_TARGET_TRIPLET}")
        if(NOT _DXAPP_TRIPLET)
            set(_DXAPP_TRIPLET "x64-windows")
        endif()

        # Default RUNTIME_OUTPUT_DIRECTORY layout; nothing here overrides it.
        get_property(_DXAPP_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
        if(_DXAPP_MULTI_CONFIG)
            set(_DXAPP_EXAMPLE_BIN_DIR "${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>")
        else()
            set(_DXAPP_EXAMPLE_BIN_DIR "${CMAKE_CURRENT_BINARY_DIR}")
        endif()

        set(_DXAPP_VCPKG_BIN "$<IF:$<CONFIG:Debug>,\
${VCPKG_INSTALLED_DIR}/${_DXAPP_TRIPLET}/debug/bin,\
${VCPKG_INSTALLED_DIR}/${_DXAPP_TRIPLET}/bin>")

        add_custom_target(dxapp_stage_vcpkg_dlls
            COMMAND ${CMAKE_COMMAND}
                    -DSRC_DIR=${_DXAPP_VCPKG_BIN}
                    -DDST_DIR=${_DXAPP_EXAMPLE_BIN_DIR}
                    -P ${PROJECT_ROOT}/cmake/stage_vcpkg_dlls.cmake
            COMMENT "Staging vcpkg runtime DLLs into the example output directory"
            VERBATIM)
    else()
        message(STATUS "cpp_example: VCPKG_INSTALLED_DIR not set, skipping runtime DLL staging")
    endif()
endif()

# =============================================================================
# Common Source Files — build once as OBJECT library instead of per-target
# =============================================================================
add_library(dxapp_common_obj OBJECT
    ${PROJECT_ROOT}/src/utility/common_util.cpp
    ${PROJECT_ROOT}/src/postprocess/sfa3d/sfa3d_postprocess.cpp
    ${PROJECT_ROOT}/src/postprocess/superpoint/superpoint_postprocess.cpp
    ${PROJECT_ROOT}/src/postprocess/dope/dope_postprocess.cpp
    ${PROJECT_ROOT}/src/postprocess/yolopv2/yolopv2_postprocess.cpp
)
target_compile_options(dxapp_common_obj PRIVATE ${COMMON_COMPILE_FLAGS})
target_compile_definitions(dxapp_common_obj PRIVATE ${COMMON_COMPILE_DEFINITIONS})
target_include_directories(dxapp_common_obj
    PRIVATE
        ${OpenCV_INCLUDE_DIRS}
        ${PROJECT_ROOT}/extern/
        ${PROJECT_ROOT}/src/utility/
        ${CPP_EXAMPLE_DIR}
        ${CPP_EXAMPLE_DIR}/common/processors
    INTERFACE
        ${PROJECT_ROOT}/src/postprocess/superpoint/
        ${PROJECT_ROOT}/src/postprocess/dope/
        ${PROJECT_ROOT}/src/postprocess/yolopv2/
)

# =============================================================================
# =============================================================================
# Helper Function to Create Example Executables
# =============================================================================
function(add_example TARGET_NAME SOURCE_FILE POSTPROCESS_DIR)
    add_executable(${TARGET_NAME}
        ${SOURCE_FILE}
    )

    target_compile_options(${TARGET_NAME} PRIVATE ${COMMON_COMPILE_FLAGS})
    target_compile_definitions(${TARGET_NAME} PRIVATE ${COMMON_COMPILE_DEFINITIONS})
    target_include_directories(${TARGET_NAME} PRIVATE
        ${CPP_EXAMPLE_DIR}
    )

    if(DXAPP_WITH_SHAREDLIB)
        target_link_directories(${TARGET_NAME} PRIVATE ${PROJECT_ROOT}/lib/)
        target_link_libraries(${TARGET_NAME} dxapp_common_obj ${COMMON_LIBS})
    else()
        target_link_libraries(${TARGET_NAME} dxapp_common_obj ${COMMON_LIBS})
    endif()

    # Windows/vcpkg only: runtime DLLs are staged once up front rather than per
    # target. The target does not exist elsewhere, so this is a no-op on Linux.
    # See the "Runtime DLL Deployment" section above.
    if(TARGET dxapp_stage_vcpkg_dlls)
        add_dependencies(${TARGET_NAME} dxapp_stage_vcpkg_dlls)
    endif()
endfunction()

# =============================================================================
# Auto-Discovery: Scan category/model directories for *_sync.cpp & *_async.cpp
# =============================================================================
# Single-model categories (each subdir = one model with {model}_sync.cpp / _async.cpp)
set(CATEGORIES
    3d_object_detection
    anomaly_detection
    depth_estimation
    face_attribute
    face_detection
    face_landmark
    face_recognition
    hand_detection
    hand_landmark
    image_classification
    image_denoising
    image_matting
    image_retrieval
    instance_segmentation
    keypoint_detection
    low_light_enhancement
    object_detection
    object_pose_estimation
    oriented_object_detection
    panoptic_driving_perception
    person_attribute
    person_reid
    pose_estimation
    semantic_segmentation
    super_resolution
    visual_place_recognition
    zero_shot_image_classification
    zero_shot_instance_segmentation
)

# One executable per variant: <task>/<family>/<variant>/<variant>_{sync,async}.cpp
function(add_variant_example VARIANT_DIR VARIANT_NAME KIND)
    set(_SRC ${VARIANT_DIR}/${VARIANT_NAME}_${KIND}.cpp)
    if(NOT EXISTS ${_SRC})
        return()
    endif()
    add_example(${VARIANT_NAME}_${KIND} ${_SRC} "")
    if(KIND STREQUAL "async" AND NOT MSVC)
        target_link_libraries(${VARIANT_NAME}_${KIND} pthread)
    endif()
endfunction()

foreach(CATEGORY ${CATEGORIES})
    file(GLOB _FAMILY_DIRS RELATIVE ${CPP_EXAMPLE_DIR}/${CATEGORY}
         ${CPP_EXAMPLE_DIR}/${CATEGORY}/*)
    foreach(FAMILY ${_FAMILY_DIRS})
        set(_FAMILY_DIR ${CPP_EXAMPLE_DIR}/${CATEGORY}/${FAMILY})
        if(NOT IS_DIRECTORY ${_FAMILY_DIR})
            continue()
        endif()

        file(GLOB _VARIANT_DIRS RELATIVE ${_FAMILY_DIR} ${_FAMILY_DIR}/*)
        foreach(VARIANT ${_VARIANT_DIRS})
            set(_VARIANT_DIR ${_FAMILY_DIR}/${VARIANT})
            if(NOT IS_DIRECTORY ${_VARIANT_DIR})
                continue()
            endif()
            add_variant_example(${_VARIANT_DIR} ${VARIANT} sync)
            add_variant_example(${_VARIANT_DIR} ${VARIANT} async)
        endforeach()
    endforeach()
endforeach()

# =============================================================================
# Multi-Model Examples (category pattern: *_x_*)
# =============================================================================
file(GLOB _MULTI_CATEGORIES RELATIVE ${CPP_EXAMPLE_DIR}
     ${CPP_EXAMPLE_DIR}/*_x_*)
foreach(MULTI_CAT ${_MULTI_CATEGORIES})
    file(GLOB _MULTI_MODELS RELATIVE ${CPP_EXAMPLE_DIR}/${MULTI_CAT}
         ${CPP_EXAMPLE_DIR}/${MULTI_CAT}/*)
    foreach(MODEL ${_MULTI_MODELS})
        set(_MODEL_DIR ${CPP_EXAMPLE_DIR}/${MULTI_CAT}/${MODEL})
        if(NOT IS_DIRECTORY ${_MODEL_DIR})
            continue()
        endif()

        if(EXISTS ${_MODEL_DIR}/${MODEL}_sync.cpp)
            add_example(${MODEL}_sync ${_MODEL_DIR}/${MODEL}_sync.cpp "")
        endif()

        if(EXISTS ${_MODEL_DIR}/${MODEL}_async.cpp)
            add_example(${MODEL}_async ${_MODEL_DIR}/${MODEL}_async.cpp "")
            if(NOT MSVC)
                target_link_libraries(${MODEL}_async pthread)
            endif()
        endif()
    endforeach()
endforeach()

# JSON pipeline runner. Factories are registered in registry.cpp; the JSON
# file selects among them. Single-model *_sync / *_async targets are unchanged.
set(MULTI_MODEL_DIR ${CPP_EXAMPLE_DIR}/multi_model)
add_executable(multi_model_run
    ${MULTI_MODEL_DIR}/main.cpp
    ${MULTI_MODEL_DIR}/pipeline.cpp
    ${MULTI_MODEL_DIR}/registry.cpp
    ${MULTI_MODEL_DIR}/runner.cpp
)
target_compile_options(multi_model_run PRIVATE ${COMMON_COMPILE_FLAGS})
target_compile_definitions(multi_model_run PRIVATE ${COMMON_COMPILE_DEFINITIONS})
target_include_directories(multi_model_run PRIVATE ${CPP_EXAMPLE_DIR})
target_link_libraries(multi_model_run dxapp_common_obj ${COMMON_LIBS})
if(TARGET dxapp_stage_vcpkg_dlls)
    add_dependencies(multi_model_run dxapp_stage_vcpkg_dlls)
endif()

# DOPE builds with core OpenCV only: the C++ visualizer draws the cuboid by
# connecting the predicted 2-D vertices directly (no solvePnP/projectPoints).

# =============================================================================
# Installation (Optional)
# =============================================================================
get_property(ALL_TARGETS DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR} PROPERTY BUILDSYSTEM_TARGETS)

set(INSTALL_TARGETS)
foreach(_TARGET ${ALL_TARGETS})
    get_target_property(_TARGET_TYPE ${_TARGET} TYPE)
    if(NOT _TARGET_TYPE STREQUAL "UTILITY")
        list(APPEND INSTALL_TARGETS ${_TARGET})
    endif()
endforeach()

install(TARGETS ${INSTALL_TARGETS} RUNTIME DESTINATION bin)

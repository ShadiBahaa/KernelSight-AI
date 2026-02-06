cmake_minimum_required(VERSION 3.20)
project(KernelSightAI VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build options
option(BUILD_TESTS "Build tests" ON)
option(BUILD_EBPF "Build eBPF programs" ON)
option(USE_RUST "Build Rust components" OFF)

# Find dependencies
find_package(Threads REQUIRED)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/src)

# Subdirectories
add_subdirectory(src/telemetry)
add_subdirectory(src/pipeline)

if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# Installation handled by setup.py

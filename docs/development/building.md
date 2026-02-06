# Building KernelSight AI

## Build System Overview

KernelSight AI uses CMake for C/C++ components and standard Python tooling for Python modules.

## Quick Build

```bash
# From project root
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

## Build Options

### CMake Options

```bash
# Build with tests
cmake -DBUILD_TESTS=ON ..

# Build eBPF programs
cmake -DBUILD_EBPF=ON ..

# Enable Rust components
cmake -DUSE_RUST=ON ..

# Debug build
cmake -DCMAKE_BUILD_TYPE=Debug ..

# Release build with optimizations
cmake -DCMAKE_BUILD_TYPE=Release ..
```

### Component-Specific Builds

```bash
# Build only telemetry collectors
make telemetry

# Build only pipeline
make pipeline

# Build specific target
make collector_binary
```

## eBPF Program Compilation

eBPF programs are compiled separately:

```bash
# Compile BPF programs (requires clang)
cd src/telemetry/ebpf
make

# This generates:
# - *.bpf.o: BPF object files
# - *.skel.h: BPF skeleton headers for C loader
```

## Python Package Build

```bash
# Install in development mode
pip install -e .

# Build distribution packages
python -m build

# This generates:
# - dist/*.whl: Wheel package
# - dist/*.tar.gz: Source distribution
```

## Targets

| Target | Description |
|--------|-------------|
| `all` | Build all components |
| `telemetry` | Build telemetry collectors |
| `pipeline` | Build data pipeline |
| `clean` | Remove build artifacts |
| `test` | Run C/C++ tests |

## Installation

```bash
# Install to system (requires root)
cd build
sudo make install

# Default install locations:
# - Binaries: /usr/local/bin
# - Configs: /etc/kernelsight
# - Libraries: /usr/local/lib
```

## Cross-Compilation

```bash
# For ARM64
cmake -DCMAKE_TOOLCHAIN_FILE=../cmake/arm64-toolchain.cmake ..

# For different kernel version
cmake -DKERNEL_HEADERS=/path/to/kernel/headers ..
```

## Troubleshooting

### Missing libbpf

```bash
# Ubuntu/Debian
sudo apt-get install libbpf-dev

# From source
git clone https://github.com/libbpf/libbpf.git
cd libbpf/src
make && sudo make install
```

### BPF Compilation Errors

```bash
# Ensure clang and llvm are installed
clang --version  # Should be 10+

# Check kernel headers
ls /usr/src/linux-headers-$(uname -r)
```

## Build Performance

```bash
# Use ccache for faster rebuilds
cmake -DCMAKE_C_COMPILER_LAUNCHER=ccache \
      -DCMAKE_CXX_COMPILER_LAUNCHER=ccache ..

# Parallel builds
make -j$(nproc)
```

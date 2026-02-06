#!/bin/bash
# Quick setup and test script for WSL
# Run this from the KernelSight AI project root

set -e

echo "======================================"
echo "KernelSight AI - Syscall Tracer Setup"
echo "======================================"
echo ""

# Check WSL environment
echo "→ Checking WSL environment..."
uname -a
echo ""

# Check kernel version (need 5.15+)
KERNEL_VERSION=$(uname -r | cut -d. -f1,2)
echo "→ Kernel version: $KERNEL_VERSION"
if [ $(echo "$KERNEL_VERSION < 5.15" | bc) -eq 1 ]; then
    echo "⚠️  WARNING: Kernel version is below 5.15. eBPF features may be limited."
else
    echo "✓ Kernel version is sufficient for eBPF"
fi
echo ""

# Install dependencies
echo "→ Installing dependencies..."

# Detect WSL2 kernel (has 'microsoft' in version)
IS_WSL=false
if uname -r | grep -qi "microsoft"; then
    IS_WSL=true
    echo "  Detected WSL2 kernel - will use BTF instead of kernel headers"
fi

sudo apt-get update

# Install base dependencies
BASE_DEPS="clang llvm libbpf-dev auditd cmake build-essential pkg-config jq"

if [ "$IS_WSL" = true ]; then
    # WSL2: Skip linux-headers (use BTF instead)
    echo "  Installing: $BASE_DEPS"
    sudo apt-get install -y $BASE_DEPS
    
    # Verify BTF is available
    if [ -f /sys/kernel/btf/vmlinux ]; then
        echo "  ✓ BTF support detected at /sys/kernel/btf/vmlinux"
    else
        echo "  ⚠️  WARNING: BTF not found. eBPF compilation may fail."
    fi
else
    # Regular Linux: Install headers
    echo "  Installing: $BASE_DEPS linux-headers-$(uname -r)"
    sudo apt-get install -y $BASE_DEPS linux-headers-$(uname -r)
fi

echo ""
echo "✓ Dependencies installed"
echo ""

# Build
echo "→ Building syscall tracer..."
mkdir -p build
cd build
cmake .. -DBUILD_EBPF=ON
make syscall_tracer -j$(nproc)

echo ""
echo "✓ Build complete!"
echo ""

# Verify build
echo "→ Verifying build artifacts..."
ls -lh src/telemetry/syscall_tracer.bpf.o
ls -lh src/telemetry/syscall_tracer
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To run the tracer:"
echo "  cd build/src/telemetry"
echo "  sudo ./syscall_tracer"
echo ""
echo "To test (in another terminal):"
echo "  sleep 1"
echo "  dd if=/dev/zero of=/tmp/test bs=1M count=100 oflag=sync"
echo ""

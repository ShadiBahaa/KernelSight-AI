#!/bin/bash
# Setup passwordless sudo for KernelSight AI tracers
# Run this ONCE: sudo ./setup_sudo.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build/src/telemetry"
USERNAME=$(logname 2>/dev/null || echo $SUDO_USER)

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo $0"
    exit 1
fi

echo "Setting up passwordless sudo for KernelSight AI tracers..."
echo "User: $USERNAME"
echo "Tracers in: $BUILD_DIR"

# Create sudoers file for KernelSight tracers
SUDOERS_FILE="/etc/sudoers.d/kernelsight"

cat > "$SUDOERS_FILE" << EOF
# KernelSight AI - Passwordless sudo for eBPF tracers
# Created by setup_sudo.sh

$USERNAME ALL=(root) NOPASSWD: $BUILD_DIR/syscall_tracer
$USERNAME ALL=(root) NOPASSWD: $BUILD_DIR/sched_tracer
$USERNAME ALL=(root) NOPASSWD: $BUILD_DIR/page_fault_tracer
$USERNAME ALL=(root) NOPASSWD: $BUILD_DIR/io_latency_tracer
$USERNAME ALL=(root) NOPASSWD: /usr/bin/stdbuf

# For agent command execution
$USERNAME ALL=(root) NOPASSWD: /usr/bin/sync
$USERNAME ALL=(root) NOPASSWD: /usr/bin/sysctl
$USERNAME ALL=(root) NOPASSWD: /usr/bin/sh -c echo*drop_caches
EOF

chmod 440 "$SUDOERS_FILE"

# Validate sudoers syntax
if visudo -c -f "$SUDOERS_FILE" 2>/dev/null; then
    echo ""
    echo "✓ Sudo configured successfully!"
    echo ""
    echo "You can now run ./start_kernelsight.sh without password prompts."
else
    echo "ERROR: Invalid sudoers syntax!"
    rm -f "$SUDOERS_FILE"
    exit 1
fi

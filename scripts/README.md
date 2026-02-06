# Scripts

Utility scripts for development and operations.

## Available Scripts

### `quick_start.sh`

One-command setup, build, and run script for all eBPF tracers. Works on Ubuntu 22.04+ and WSL2.

**Basic Usage**:
```bash
# Install dependencies and build all tracers
./quick_start.sh

# Install, build, and run syscall tracer
./quick_start.sh --run syscall

# Install, build, and run scheduler tracer
./quick_start.sh --run scheduler

# Install, build, and run BOTH tracers in tmux
./quick_start.sh --run all
```

**What it does**:
- Detects WSL2 vs native Linux environment
- Installs all required dependencies (clang, libbpf, bpftool, etc.)
- Generates vmlinux.h from BTF (if available)
- Generates syscall names mapping
- Builds all eBPF tracers
- Optionally runs tracers with proper permissions

**Running both tracers simultaneously**:
```bash
./quick_start.sh --run all

# This creates a tmux session 'kernelsight' with two windows:
# - Window 1: syscall tracer
# - Window 2: scheduler tracer

# Attach to view the tracers:
tmux attach -t kernelsight

# Switch between tracers:
# Ctrl+B then '1' for syscall
# Ctrl+B then '2' for scheduler

# Detach (tracers keep running):
# Ctrl+B then 'd'

# Kill all tracers:
tmux kill-session -t kernelsight
```

### `setup_wsl.sh`

WSL2-specific setup script for kernel configuration and dependencies.

### `generate_syscall_names.sh`

Generates syscall name mappings from `ausyscall` for the syscall tracer.

**Usage**:
```bash
./generate_syscall_names.sh src/telemetry/common/syscall_names.h
```

## Scripts To Be Created

- `generate-test-data.py`: Generate synthetic telemetry data
- `train-models.py`: Train ML models
- `benchmark.sh`: Performance benchmarking
- `migrate-db.py`: Database migration tools

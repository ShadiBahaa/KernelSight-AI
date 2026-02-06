# Building the High-Latency Syscall Tracer

## System Requirements

**Supported Platform**: Ubuntu 22.04 LTS or newer

**Minimum Kernel**: Linux 5.15+ with eBPF support

> **Note**: This project is developed and tested exclusively on Ubuntu 22.04+ LTS. While it may work on other Linux distributions, they are not officially supported.

## Prerequisites

Install all required dependencies:

```bash
sudo apt-get update
sudo apt-get install -y \\
    clang \\
    llvm \\
    libbpf-dev \\
    auditd \\
    linux-headers-$(uname -r) \\
    cmake \\
    build-essential \\
    pkg-config
```

### Dependency Breakdown

| Package | Purpose |
|---------|---------|
| `clang` | Compiles eBPF programs to BPF bytecode |
| `llvm` | Provides BPF toolchain (llvm-strip, etc.) |
| `libbpf-dev` | Userspace library for BPF loading |
| `auditd` | Provides `ausyscall` for syscall name generation |
| `linux-headers` | Kernel headers for BPF compilation |
| `cmake` | Build system |
| `build-essential` | C compiler and standard tools |
| `pkg-config` | Dependency detection |

## Build Instructions

### 1. Configure the Build

From the project root directory:

```bash
mkdir -p build
cd build
cmake .. -DBUILD_EBPF=ON
```

CMake will automatically:
- Check for all required dependencies
- Generate syscall name mappings from `ausyscall --dump`
- Configure the build system

**If dependencies are missing**, CMake will fail with clear installation instructions.

### 2. Compile the Tracer

```bash
make syscall_tracer -j$(nproc)
```

This will:
1. Generate `src/telemetry/common/syscall_names.h` from ausyscall (required)
2. Compile `syscall_tracer.bpf.c` to `syscall_tracer.bpf.o` using clang
3. Build the userspace loader `syscall_tracer`
4. Link with libbpf library

> **Note**: Syscall name generation is **mandatory**. If `ausyscall` is not available, the build will fail. This ensures we never use outdated syscall mappings.

### 3. Verify the Build

```bash
# Check BPF object was created
ls -lh build/src/telemetry/syscall_tracer.bpf.o

# Check executable exists
ls -lh build/src/telemetry/syscall_tracer

# Verify BPF object is valid
llvm-objdump -h build/src/telemetry/syscall_tracer.bpf.o
```

Expected output shows BPF sections like `.text`, `maps`, `license`, etc.

## Running the Tracer

> **Important**: The tracer requires root privileges to load eBPF programs.

```bash
# Run from build directory
cd build/src/telemetry
sudo ./syscall_tracer
```

Expected output:
```
Loading eBPF program...
BPF program loaded successfully
BPF programs attached to tracepoints
Tracing syscalls with latency >10ms... Press Ctrl+C to exit
```

### Example JSON Output

```json
{
  "timestamp": 1735424651234567890,
  "time_str": "2025-12-28 21:04:11",
  "pid": 1234,
  "tid": 1235,
  "cpu": 2,
  "uid": 1000,
  "syscall": 35,
  "syscall_name": "nanosleep",
  "latency_ms": 1000.123,
  "ret_value": 0,
  "is_error": false,
  "comm": "sleep"
}
```

## Troubleshooting

### CMake Fails with Missing Dependencies

**Error**: `Missing required dependencies for eBPF build: ...`

**Solution**: Install the missing packages as shown in the error message:
```bash
sudo apt-get install -y clang llvm libbpf-dev auditd linux-headers-$(uname -r)
```

### "failed to open BPF object file"

**Error**: `ERROR: failed to open BPF object file`

**Causes**:
- syscall_tracer.bpf.o not in the same directory as the executable
- BPF object wasn't built

**Solution**:
```bash
# Run from build/src/telemetry directory
cd build/src/telemetry
sudo ./syscall_tracer
```

### "failed to load BPF object"

**Possible Causes**:
- **Not running as root**: Use `sudo`
- **Kernel too old**: Requires Linux 5.15+ with eBPF support
- **BTF not enabled**: Check if `/sys/kernel/btf/vmlinux` exists
- **Missing kernel headers**: Install `linux-headers-$(uname -r)`

**Verify kernel support**:
```bash
# Check kernel version
uname -r

# Check BTF availability
ls -l /sys/kernel/btf/vmlinux

# Check BPF is enabled
zgrep CONFIG_BPF /proc/config.gz
```

###"failed to attach tracepoint"

**Verify tracepoints exist**:
```bash
ls /sys/kernel/debug/tracing/events/raw_syscalls/
```

**Ensure tracefs is mounted**:
```bash
sudo mount -t tracefs none /sys/kernel/debug/tracing
```

## Testing

Generate high-latency syscalls for testing:

```bash
# In another terminal

# ~1 second nanosleep syscall
sleep 1

# ~500ms nanosleep  
sleep 0.5

# Slow disk I/O (write syscalls)
dd if=/dev/zero of=/tmp/test bs=1M count=1000 oflag=sync

# Network I/O (read/write syscalls)
curl -s https://example.com > /dev/null
```

You should see JSON events appear in the tracer output for syscalls exceeding 10ms.

## Advanced: Manual Syscall Name Generation

If you want to regenerate the syscall name header manually:

```bash
# From project root
bash scripts/generate_syscall_names.sh src/telemetry/common/syscall_names.h

# Verify output
head -n 30 src/telemetry/common/syscall_names.h
```

This uses `ausyscall --dump` to get the complete and accurate syscall table for your architecture.


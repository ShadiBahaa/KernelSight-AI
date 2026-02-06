# Quick Start Guide - KernelSight AI eBPF Tracers

This guide shows you how to get all the eBPF tracers up and running with a single command.

## Prerequisites

- Linux system (Ubuntu 22.04+ recommended) or WSL2
- `sudo` access
- Internet connection (for installing dependencies)

## One-Command Setup

The `quick_start.sh` script handles everything automatically:

### 1. Install Dependencies & Build All Tracers

```bash
cd /path/to/KernelSight\ AI
./scripts/quick_start.sh
```

This will:
- ✅ Install all dependencies (clang, libbpf, bpftool, etc.)
- ✅ Detect WSL2 vs native Linux
- ✅ Generate vmlinux.h from kernel BTF
- ✅ Generate syscall name mappings
- ✅ Build both syscall and scheduler tracers
- ✅ Verify all artifacts

**Output:**
```
==========================================
KernelSight AI - eBPF Tracers
One-Command Setup & Build
==========================================

→ Checking environment...
  Kernel: 5.15.0-91-generic
  OS: Ubuntu 22.04.3 LTS

→ Installing dependencies...
  ✓ Dependencies installed

→ Building eBPF tracers...
  ✓ Build complete!

→ Build verification
  ✓ Syscall Tracer:
    - Executable: syscall_tracer 18K
    - BPF object: syscall_tracer.bpf.o 52K
  ✓ Scheduler Tracer:
    - Executable: sched_tracer 19K
    - BPF object: sched_tracer.bpf.o 48K

==========================================
Setup Complete!
==========================================
```

### 2. Run Individual Tracers

**Syscall Tracer** (captures high-latency system calls):
```bash
./scripts/quick_start.sh --run syscall
```

**Scheduler Tracer** (captures context switches and CPU time):
```bash
./scripts/quick_start.sh --run scheduler
```

### 3. Run Both Tracers Simultaneously

```bash
./scripts/quick_start.sh --run all
```

This creates a tmux session with both tracers running in separate windows.

**Tmux Session Management:**
```bash
# Attach to the running session
tmux attach -t kernelsight

# Inside tmux:
# - Ctrl+B then '1' → Switch to syscall tracer
# - Ctrl+B then '2' → Switch to scheduler tracer
# - Ctrl+B then 'd' → Detach (tracers keep running)
# - Ctrl+C → Stop current tracer

# Kill all tracers
tmux kill-session -t kernelsight
```

## Example Usage

### Test Syscall Tracer

In one terminal:
```bash
./scripts/quick_start.sh --run syscall
```

In another terminal, generate high-latency syscalls:
```bash
# Sleep syscall (1 second)
sleep 1

# Sync I/O operations
dd if=/dev/zero of=/tmp/test bs=1M count=100 oflag=sync
```

**Expected Output:**
```json
{
  "timestamp": 1735410686234567890,
  "time_str": "2025-12-30 16:45:06",
  "pid": 12345,
  "tid": 12345,
  "cpu": 2,
  "uid": 1000,
  "syscall": 35,
  "syscall_name": "nanosleep",
  "latency_ms": 1000.123,
  "ret_value": 0,
  "is_error": false,
  "arg0": 140735268091904,
  "comm": "sleep"
}
```

### Test Scheduler Tracer

In one terminal:
```bash
./scripts/quick_start.sh --run scheduler
```

In another terminal, generate CPU load:
```bash
# CPU stress test
stress-ng --cpu 4 --timeout 30s

# Or mix of CPU and I/O
stress-ng --cpu 2 --io 2 --timeout 30s
```

**Expected Output:**
```json
{
  "time_bucket": 1735410686,
  "pid": 23456,
  "comm": "stress-ng-cpu",
  "context_switches": 856,
  "voluntary_switches": 42,
  "involuntary_switches": 814,
  "wakeups": 45,
  "cpu_time_ms": 987.234,
  "avg_timeslice_us": 1153.065
}
```

## Understanding the Output

### Syscall Tracer Fields

| Field | Description |
|-------|-------------|
| `timestamp` | Event time in nanoseconds |
| `syscall_name` | Name of the system call |
| `latency_ms` | How long the syscall took (milliseconds) |
| `is_error` | Whether syscall returned an error |
| `comm` | Process name |

### Scheduler Tracer Fields

| Field | Description |
|-------|-------------|
| `time_bucket` | 1-second bucket timestamp |
| `context_switches` | Total switches in this second |
| `voluntary_switches` | I/O-bound behavior (process yielded CPU) |
| `involuntary_switches` | CPU-bound behavior (process preempted) |
| `wakeups` | Times process was woken from sleep |
| `cpu_time_ms` | Total CPU time used |
| `avg_timeslice_us` | Average time quantum per schedule |

**Analysis Tips:**
- **High involuntary switches** → Process is CPU-bound
- **High voluntary switches** → Process is I/O-bound
- **High wakeups** → Process frequently blocks/wakes (e.g., network server)
- **Low avg_timeslice** → High CPU contention

## Advanced Usage

### Save Output to File

```bash
# Syscall tracer with JSON output
sudo ./build/src/telemetry/syscall_tracer > syscalls.json 2>&1

# Scheduler tracer with JSON output
sudo ./build/src/telemetry/sched_tracer > scheduler_events.json 2>&1
```

### Filter Specific Processes

Use `jq` to filter output:

```bash
# Only show events from 'stress-ng' processes
sudo ./build/src/telemetry/sched_tracer | jq 'select(.comm | contains("stress"))'

# Show only high context-switch processes (>100/sec)
sudo ./build/src/telemetry/sched_tracer | jq 'select(.context_switches > 100)'
```

### Run in Background

```bash
# Run tracers in background, redirect to files
cd build/src/telemetry
sudo ./syscall_tracer > /var/log/syscalls.json 2>&1 &
sudo ./sched_tracer > /var/log/scheduler.json 2>&1 &

# Check they're running
ps aux | grep tracer

# Kill when done
sudo pkill syscall_tracer
sudo pkill sched_tracer
```

## Troubleshooting

### Permission Denied

eBPF programs require root privileges:
```bash
sudo ./scripts/quick_start.sh --run syscall
```

### BTF Not Available

If you see "BTF not found" warning:
- On native Linux: Install `linux-headers-$(uname -r)`
- On WSL2: BTF should be available by default in recent versions
- The tracers will still work, just with fallback type definitions

### Build Failures

1. **Missing dependencies**: Re-run the setup portion
   ```bash
   ./scripts/quick_start.sh
   ```

2. **Stale CMake cache**: Clean and rebuild
   ```bash
   rm -rf build
   ./scripts/quick_start.sh
   ```

3. **WSL2 kernel too old**: Update WSL2
   ```bash
   wsl --update
   ```

## Next Steps

Once you have the tracers running:

1. **Collect baseline data** from your system under normal load
2. **Generate test workloads** to validate the tracers
3. **Integrate with pipeline** to feed data into storage/ML layers
4. **Set up dashboards** to visualize the metrics

## Script Reference

```bash
# Full command syntax
./scripts/quick_start.sh [--run <type>]

# Where <type> is:
#   syscall    - Run syscall tracer only
#   scheduler  - Run scheduler tracer only  
#   all        - Run both in tmux session
#   (omit)     - Just build, don't run
```

## Questions?

See the full documentation:
- [eBPF Tracers README](../src/telemetry/ebpf/README.md)
- [Build Instructions](../src/telemetry/ebpf/BUILD.md)
- [Architecture Overview](../docs/architecture/overview.md)

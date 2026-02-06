# eBPF Programs for KernelSight AI

This directory contains eBPF (Extended Berkeley Packet Filter) programs for deep kernel telemetry collection.

## Overview

eBPF allows running sandboxed programs in the Linux kernel without changing kernel source code or loading kernel modules. Our eBPF programs attach to various kernel events to collect performance metrics with minimal overhead.

## Implemented Programs

### 1. High-Latency Syscall Tracer

**Files**: `syscall_tracer.bpf.c` (kernel), `syscall_tracer.c` (userspace)

Monitors all system calls and captures those exceeding 10ms latency. Useful for identifying performance bottlenecks in applications.

**Features**:
- Attaches to `raw_syscalls/sys_enter` and `sys_exit` tracepoints
- Filters syscalls with latency >10ms
- Outputs JSON events via efficient ring buffer
- Zero-copy data transfer from kernel to userspace
- Minimal performance overhead

**Output Example**:
```json
{
  "timestamp": 1735410686234567890,
  "time_str": "2025-12-28 20:18:06",
  "pid": 1234,
  "tid": 1235,
  "syscall": 35,
  "syscall_name": "nanosleep",
  "latency_ms": 1000.123,
  "comm": "sleep"
}
```

**Build & Run**: See [BUILD.md](BUILD.md)

### 2. Scheduler Events Tracer (Day 3)

**Files**: `sched_tracer.bpf.c` (kernel), `sched_tracer.c` (userspace)

Monitors scheduler events (`sched_switch` and `sched_wakeup`) to track per-process context switch rates and CPU time. Aggregates data into 1-second buckets for efficient analysis.

**Features**:
- Attaches to `sched/sched_switch` and `sched/sched_wakeup` tracepoints
- Tracks voluntary vs involuntary context switches
- Computes per-process CPU time and average timeslice
- Aggregates events into 1-second buckets (in-kernel)
- Emits only aggregated data to minimize overhead

**Output Example**:
```json
{
  "time_bucket": 1234567890,
  "pid": 5678,
  "comm": "stress-ng",
  "context_switches": 142,
  "voluntary_switches": 38,
  "involuntary_switches": 104,
  "wakeups": 156,
  "cpu_time_ms": 856.234,
  "avg_timeslice_us": 6032.127
}
```

**Use Cases**:
- Identify processes with excessive context switching
- Detect CPU-bound vs I/O-bound behavior
- Analyze scheduler fairness and performance
- Correlate context switches with application latency

**Build & Run**: See [BUILD.md](BUILD.md)

## Programs To Be Implemented

- `page_faults.bpf.c`: Page fault monitoring
- `io_latency.bpf.c`: Block I/O latency distribution
- `tcp_retrans.bpf.c`: TCP retransmit tracking
- `net_traffic.bpf.c`: Network traffic monitoring

## Architecture

```
┌─────────────────────────────────────────┐
│ Userspace Loader (C + libbpf)           │
│ - Loads BPF program                     │
│ - Consumes ring buffer events           │
│ - Outputs JSON                          │
└──────────────┬──────────────────────────┘
               │ Ring Buffer
               │ (zero-copy)
┌──────────────▼──────────────────────────┐
│ eBPF Program (Kernel Space)             │
│ - Attached to tracepoints               │
│ - Filters events                        │
│ - Collects metrics                      │
└─────────────────────────────────────────┘
```

## Development Guidelines

### Writing eBPF Programs

1. **Use CO-RE (Compile Once, Run Everywhere)**: Leverage BPF CO-RE for kernel version portability
2. **Minimize overhead**: Keep BPF program logic simple and fast
3. **Use ring buffers**: Prefer ring buffers over perf buffers for better performance
4. **Validate data**: Always validate pointers and data sizes
5. **Error handling**: BPF programs must never crash - handle all edge cases

### Testing eBPF Programs

```bash
# Check BPF object is valid
llvm-objdump -h syscall_tracer.bpf.o

# Load and verify with bpftool
sudo bpftool prog load syscall_tracer.bpf.o /sys/fs/bpf/test

# Check loaded programs
sudo bpftool prog list

# View BPF maps
sudo bpftool map list
```

## Resources

- [BPF Documentation](https://docs.kernel.org/bpf/)
- [libbpf GitHub](https://github.com/libbpf/libbpf)
- [BCC Tools](https://github.com/iovisor/bcc)
- [eBPF Summit](https://ebpf.io/summit-2024/)


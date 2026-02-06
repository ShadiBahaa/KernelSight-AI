# Telemetry Collection

This directory contains the low-level telemetry collection components.

## Structure

- `ebpf/`: eBPF programs for in-kernel data collection
- `perf/`: Perf event collectors
- `sysfs/`: Sysfs/Procfs scrapers
- `common/`: Shared utilities

## Building

See [../../docs/development/building.md](../../docs/development/building.md)

## Components To Be Implemented

- [x] eBPF high-latency syscall tracer (>10ms)
- [x] eBPF scheduler latency collector
- [x] eBPF page fault tracer
- [x] eBPF I/O latency tracer
- [x] Procfs CPU stats scraper
- [x] Sysfs disk metrics scraper
- [x] Network statistics collector

## Implemented Components

### High-Latency Syscall Tracer

Captures system calls with latency exceeding 10ms using eBPF tracepoints. Outputs JSON events via ring buffer for efficient processing.

**Location**: `ebpf/syscall_tracer.bpf.c` (kernel), `ebpf/syscall_tracer.c` (userspace)

**Build instructions**: See [ebpf/BUILD.md](ebpf/BUILD.md)

**Usage**:
```bash
sudo ./build/telemetry/syscall_tracer
```

### Page Fault Tracer

Captures page fault events with latency measurements and fault type classification (major vs minor). Attaches to kernel page fault handlers and measures fault resolution time.

**Location**: `ebpf/page_fault_tracer.bpf.c` (kernel), `ebpf/page_fault_tracer.c` (userspace)

**Usage**:
```bash
sudo ./build/telemetry/page_fault_tracer
# Or pipe to jq for pretty-printing
sudo ./build/telemetry/page_fault_tracer | jq .
```

**Metrics**:
- Minor vs major page faults
- Fault handling latency (nanoseconds/microseconds)
- Faulting address and process details
- Read vs write faults
- User vs kernel mode faults

### I/O Latency Tracer

Measures block I/O request latency with histogram-based percentile calculation. Tracks separate statistics for read and write operations.

**Location**: `ebpf/io_latency_tracer.bpf.c` (kernel), `ebpf/io_latency_tracer.c` (userspace)

**Usage**:
```bash
sudo ./build/telemetry/io_latency_tracer
# Output shows p50, p95, p99 latencies every second
sudo ./build/telemetry/io_latency_tracer | jq .
```

**Metrics**:
- Read/write operation counts and bytes
- p50, p95, p99 latency percentiles (microseconds)
- Maximum latency per operation type
- 1-second aggregation intervals

### Sysfs/Procfs Scraper Daemon

Periodically scrapes `/proc/meminfo`, `/proc/loadavg`, `/sys/block/*/stat`, `/proc/net/dev`, `/proc/net/tcp`, and `/proc/net/snmp` for system metrics. Polls every 1 second and emits JSON streams to stdout.

**Location**: `sysfs/scraper_daemon.c`, `sysfs/proc_scraper.c`, `sysfs/sysfs_scraper.c`, `sysfs/net_stats.c`

**Usage**:
```bash
./build/telemetry/scraper_daemon
# Or redirect to a file
./build/telemetry/scraper_daemon > metrics.json
# Or pipe to jq for pretty-printing
./build/telemetry/scraper_daemon | jq .
```

**Collected Metrics**:
- **Memory**: total, free, available, buffers, cached, swap, active, inactive, dirty, writeback
- **Load**: 1/5/15-minute averages, running/total processes
- **Block I/O**: per-device read/write operations, sectors, latency, queue depth
- **Network interfaces**: per-interface RX/TX bytes, packets, errors, drops
- **TCP connections**: connection states (established, time_wait, close_wait, etc.)
- **TCP retransmits**: total retransmitted segments

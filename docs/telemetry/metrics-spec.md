# KernelSight AI - Telemetry Metrics Specification

This document defines the complete set of metrics collected by KernelSight AI's telemetry subsystem.

## Overview

KernelSight AI collects metrics across four primary domains:
- **CPU**: Scheduler performance and utilization
- **Memory**: Allocation patterns and pressure
- **I/O**: Block device and filesystem performance
- **Network**: Connection states and throughput

## CPU Metrics

### Scheduler Latency
**Source**: eBPF program attached to scheduler tracepoints  
**Collection Interval**: Real-time (per-event)  
**Format**: Histogram (microseconds)

Measures time from task wakeup to actual CPU assignment. Critical for identifying scheduling bottlenecks.

**Metrics**:
- `sched.latency.p50`: 50th percentile latency
- `sched.latency.p95`: 95th percentile latency
- `sched.latency.p99`: 99th percentile latency
- `sched.latency.max`: Maximum latency

### CPU Utilization
**Source**: `/proc/stat`  
**Collection Interval**: 1 second  
**Format**: Percentage per CPU core

**Metrics**:
- `cpu.util.user[core_id]`: User-space utilization
- `cpu.util.system[core_id]`: Kernel-space utilization
- `cpu.util.idle[core_id]`: Idle percentage
- `cpu.util.iowait[core_id]`: I/O wait percentage

### Context Switches
**Source**: perf events (`sched:sched_switch`)  
**Collection Interval**: Aggregated per second  
**Format**: Counter

**Metrics**:
- `cpu.context_switches.voluntary`: Voluntary context switches
- `cpu.context_switches.involuntary`: Involuntary context switches

### Runqueue Depth
**Source**: `/proc/schedstat`  
**Collection Interval**: 1 second  
**Format**: Gauge

**Metrics**:
- `cpu.runqueue.depth[core_id]`: Number of waiting tasks

## Memory Metrics

### Page Faults
**Source**: eBPF program attached to page fault handlers  
**Collection Interval**: Real-time (per-event)  
**Format**: Counter + histogram

**Metrics**:
- `mem.page_faults.minor`: Minor page faults (no disk I/O)
- `mem.page_faults.major`: Major page faults (disk I/O required)
- `mem.page_faults.latency.p99`: 99th percentile fault handling time

### Memory Pressure (PSI)
**Source**: `/proc/pressure/memory`  
**Collection Interval**: 1 second  
**Format**: Percentage

**Metrics**:
- `mem.pressure.some.avg10`: % time some tasks stalled (10s avg)
- `mem.pressure.some.avg60`: % time some tasks stalled (60s avg)
- `mem.pressure.full.avg10`: % time all tasks stalled (10s avg)
- `mem.pressure.full.avg60`: % time all tasks stalled (60s avg)

### OOM Events
**Source**: Kernel trace events (`oom:mark_victim`)  
**Collection Interval**: Real-time (per-event)  
**Format**: Event log

**Metrics**:
- `mem.oom.events`: Count of OOM kills
- `mem.oom.victims[pid]`: PIDs of killed processes

### Slab Allocator Statistics
**Source**: `/proc/slabinfo`  
**Collection Interval**: 5 seconds  
**Format**: Gauge

**Metrics**:
- `mem.slab.active_objs`: Number of active objects
- `mem.slab.total_objs`: Total number of objects
- `mem.slab.utilization`: Slab utilization percentage

## I/O Metrics

### Block I/O Latency
**Source**: eBPF program on `block:block_rq_complete`  
**Collection Interval**: Real-time (per-request)  
**Format**: Histogram (microseconds)

**Metrics**:
- `io.latency.read.p50`: Read latency 50th percentile
- `io.latency.read.p95`: Read latency 95th percentile
- `io.latency.read.p99`: Read latency 99th percentile
- `io.latency.write.p50`: Write latency 50th percentile
- `io.latency.write.p95`: Write latency 95th percentile
- `io.latency.write.p99`: Write latency 99th percentile

### IOPS and Throughput
**Source**: `/proc/diskstats`  
**Collection Interval**: 1 second  
**Format**: Rate (operations/sec, bytes/sec)

**Metrics**:
- `io.ops.read[device]`: Read operations per second
- `io.ops.write[device]`: Write operations per second
- `io.throughput.read[device]`: Read bytes per second
- `io.throughput.write[device]`: Write bytes per second

### Disk Queue Depth
**Source**: `/sys/block/[device]/queue/nr_requests`  
**Collection Interval**: 1 second  
**Format**: Gauge

**Metrics**:
- `io.queue.depth[device]`: Current queue depth
- `io.queue.max[device]`: Maximum queue depth

### Filesystem Operations
**Source**: eBPF programs on VFS functions  
**Collection Interval**: Real-time (aggregated)  
**Format**: Counter

**Metrics**:
- `fs.ops.open`: File open operations per second
- `fs.ops.read`: Read operations per second
- `fs.ops.write`: Write operations per second
- `fs.ops.sync`: Sync operations per second

## Network Metrics

### TCP Retransmits
**Source**: netstat (`/proc/net/snmp`) or eBPF on `tcp_retransmit_skb`  
**Collection Interval**: 1 second  
**Format**: Counter

**Metrics**:
- `net.tcp.retransmits`: Total retransmit count
- `net.tcp.retransmit_rate`: Retransmits per second

### Network Throughput
**Source**: `/proc/net/dev`  
**Collection Interval**: 1 second  
**Format**: Rate (bytes/sec)

**Metrics**:
- `net.throughput.rx[interface]`: Receive bytes per second
- `net.throughput.tx[interface]`: Transmit bytes per second
- `net.throughput.rx_packets[interface]`: Receive packets per second
- `net.throughput.tx_packets[interface]`: Transmit packets per second

### Connection States
**Source**: `/proc/net/tcp`, `/proc/net/tcp6`  
**Collection Interval**: 5 seconds  
**Format**: Gauge

**Metrics**:
- `net.connections.established`: Established connections
- `net.connections.time_wait`: TIME_WAIT state connections
- `net.connections.close_wait`: CLOSE_WAIT state connections

### Packet Drops
**Source**: `/proc/net/dev` or eBPF on `kfree_skb`  
**Collection Interval**: 1 second  
**Format**: Counter

**Metrics**:
- `net.drops.rx[interface]`: Receive packet drops
- `net.drops.tx[interface]`: Transmit packet drops

## Data Format and Storage

### Time Series Format
All metrics are stored with:
- **Timestamp**: Unix nanoseconds
- **Metric Name**: Hierarchical dot notation
- **Value**: Float64 or Int64
- **Tags**: Key-value pairs (e.g., `device=sda`, `core_id=0`)

### Storage Backend
- **Development**: SQLite with time-series optimizations
- **Production**: InfluxDB or TimescaleDB for scalability

### Retention Policy
- **Raw data**: 24 hours at full resolution
- **1-minute aggregates**: 7 days
- **1-hour aggregates**: 30 days
- **Daily aggregates**: 1 year

## Collection Architecture

```
┌─────────────┐
│ eBPF Progs  │ ─┐
└─────────────┘  │
┌─────────────┐  │
│ Perf Events │ ─┤
└─────────────┘  ├──> Ring Buffers ──> Aggregation ──> Storage
┌─────────────┐  │                      (C++/Python)     (SQLite)
│ Procfs      │ ─┤
└─────────────┘  │
┌─────────────┐  │
│ Sysfs       │ ─┘
└─────────────┘
```

## Future Enhancements

- Hardware PMU counters (cache misses, branch mispredicts)
- GPU metrics (for AI workloads)
- Container-aware metrics (cgroups)
- Application-level tracing (distributed tracing integration)

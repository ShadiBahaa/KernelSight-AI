# Comprehensive Stress Test Guide

## Overview

The comprehensive stress test validates the **complete KernelSight AI pipeline** by:
- Running **all collectors** (scraper + eBPF tracers)
- Generating **system stress** (CPU, memory, I/O)
- Capturing **all 10 event types**
- Validating data integrity

## Quick Start

```bash
# Make executable
chmod +x scripts/stress_test_full.sh

# Run (requires root for eBPF)
sudo ./scripts/stress_test_full.sh

# Custom duration (default 60s)
sudo TEST_DURATION=120 ./scripts/stress_test_full.sh
```

## Prerequisites

### Required
- Root access (for eBPF tracers)
- All collectors built (`cmake` + `make` in build/)
- Python 3.8+

### Optional
- `stress` tool for workload generation:
  ```bash
  sudo apt-get install stress
  ```

## What It Tests

### Collectors Started
1. **scraper_daemon** - System metrics
2. **syscall_tracer** - High-latency syscalls (eBPF)
3. **io_latency_tracer** - I/O performance (eBPF)
4. **page_fault_tracer** - Memory faults (eBPF, if built)

### Stress Workloads
- **CPU**: 4 workers at 100%
- **Memory**: 1GB allocation stress
- **I/O**: Disk read/write operations
- **Network**: HTTP server + client requests + TCP connection bursts
- **File operations**: Heavy syscall activity

### Expected Event Types
1. ✓ syscall_events
2. ✓ page_fault_events
3. ✓ io_latency_stats
4. ✓ memory_metrics
5. ✓ load_metrics
6. ✓ block_stats
7. ✓ network_interface_stats
8. ✓ tcp_stats
9. ✓ tcp_retransmit_stats
10. sched_events (if scheduler tracer implemented)

## Expected Output

```
╔══════════════════════════════════════════════════════════════╗
║   KernelSight AI - Comprehensive Stress Test                ║
║   All Collectors + System Stress + Full Validation          ║
╚══════════════════════════════════════════════════════════════╝

[1/6] Checking Prerequisites
✓ Prerequisites checked

[2/6] Initializing Database
✓ Database initialized

[3/6] Starting Ingestion Daemon
  Ingestion daemon PID: 12345
✓ Ingestion daemon started

[4/6] Starting All Collectors
  Starting scraper_daemon...
  Starting syscall_tracer (eBPF)...
  Starting io_latency_tracer (eBPF)...
  Starting page_fault_tracer (eBPF)...
✓ All collectors started

[5/6] Generating System Stress (60s)
  Workloads running in background...
    - CPU stress (4 workers)
    - Memory stress (1GB)
    - I/O stress
    - Heavy disk I/O
    - File system operations
    - Network stress (HTTP server + client)
    - HTTP client requests
    - TCP connection bursts

  Progress: [==================================================] 60/60s
✓ Stress test complete

[6/6] Stopping Collectors & Analyzing Results

═══════════════════════════════════════════════════════════
                    TEST RESULTS
═══════════════════════════════════════════════════════════

Total Events Collected: 2500

Event Types Captured:

  ✓ syscall_events                    45 rows  (eBPF Syscall Tracer)
  ✓ page_fault_events                 234 rows  (eBPF Page Fault Tracer)
  ✓ io_latency_stats                  60 rows  (eBPF I/O Latency Tracer)
  ✗ sched_events                      0 rows  (eBPF Scheduler Tracer) ← NOT CAPTURED
  ✓ memory_metrics                    60 rows  (Scraper Daemon)
  ✓ load_metrics                      60 rows  (Scraper Daemon)
  ✓ block_stats                       1080 rows  (Scraper Daemon)
  ✓ network_interface_stats           120 rows  (Scraper Daemon)
  ✓ tcp_stats                         60 rows  (Scraper Daemon)
  ✓ tcp_retransmit_stats              60 rows  (Scraper Daemon)

────────────────────────────────────────────────────────
Captured: 9/10 event types
Missing:  1/10 event types

✓ PARTIAL SUCCESS - 9 event types captured
  Missing events likely due to:
    - eBPF tracers not built/running
    - Insufficient stress to trigger events

Sample Slow Syscalls:
  find       | read       | 45.23ms
  cat        | open       | 32.15ms
  dd         | write      | 28.67ms

Page Fault Summary:
  major      faults:   134 (avg: 1245.32μs)
  minor      faults:   100 (avg: 12.45μs)

═══════════════════════════════════════════════════════════
Test Complete!
═══════════════════════════════════════════════════════════

Database: data/stress_test.db
Logs: logs/stress_test/
```

## Troubleshooting

### Issue: "Must run as root"
**Solution**: Run with sudo
```bash
sudo ./scripts/stress_test_full.sh
```

### Issue: Missing eBPF events
**Check**:
```bash
# Verify tracers are built
ls -l build/src/telemetry/*_tracer

# Check if tracers started
ps aux | grep tracer

# Check logs for errors
tail -f logs/stress_test/syscall.log
tail -f logs/stress_test/io.log
```

### Issue: No stress workload
**Install stress tool**:
```bash
sudo apt-get install stress
```

### Issue: Low event counts
**Run longer**:
```bash
sudo TEST_DURATION=300 ./scripts/stress_test_full.sh
```

## Analyzing Results

After the test, explore the data:

```bash
# Use query utilities
python3 src/pipeline/query_utils.py --db-path data/stress_test.db --demo

# Direct SQL queries
sqlite3 data/stress_test.db
```

### Useful Queries

**Top slow syscalls:**
```sql
SELECT comm, syscall_name, latency_ns / 1000000.0 as latency_ms
FROM syscall_events
ORDER BY latency_ns DESC
LIMIT 10;
```

**Page fault distribution:**
```sql
SELECT fault_type, COUNT(*) as count, 
       AVG(latency_ns) / 1000.0 as avg_us
FROM page_fault_events
GROUP BY fault_type;
```

**I/O latency trends:**
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    read_p95_us, write_p95_us
FROM io_latency_stats
ORDER BY timestamp DESC
LIMIT 10;
```

## Success Criteria

- ✅ **All collectors start** without errors
- ✅ **8-10 event types** captured (9-10 is ideal)
- ✅ **Zero parse/insert errors**
- ✅ **2000+ events** in 60 seconds
- ✅ **eBPF events present** (syscall, page_fault, io_latency)

## Next Steps

After successful stress test:
1. Run longer tests (hours) for stability
2. Analyze event correlations
3. Tune batch sizes for your workload
4. Set up continuous collection
5. Integrate with Gemini 3 AI agent

# Data Pipeline Documentation

## Overview

The KernelSight AI data pipeline provides a complete solution for ingesting, storing, and querying kernel telemetry data from multiple sources. The pipeline is designed to handle high-throughput event streams while maintaining query performance.

> **Note**: For running the complete system (including semantic classifiers and agents), use `./start_kernelsight.sh`. This document covers the low-level pipeline internals.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Telemetry Collectors                       │
├───────────────┬────────────────┬────────────────┬───────────────┤
│ eBPF Tracers  │ Sysfs Scrapers │ Procfs Scrapers│ Perf Counters │
│  - Syscalls   │  - Block I/O   │  - Memory      │  - CPU PMU    │
│  - Page Faults│  - Network     │  - Load Avg    │  - Cache Miss │
│  - I/O Latency│                │  - TCP Stats   │               │
└───────┬───────┴────────┬───────┴────────┬───────┴───────┬───────┘
        │                │                │               │
        │ JSON Events (one per line via stdout)           │
        └────────────────┴────────────────┴───────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ Ingestion Daemon       │
                    │  - Event Identification│
                    │  - Normalization       │
                    │  - Batch Insertion     │
                    │  - Error Handling      │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │    SQLite Database     │
                    │  - WAL Mode            │
                    │  - Strategic Indexes   │
                    │  - 12+ Tables          │
                    │  - Views for Common    │
                    │    Queries             │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │   Query API            │
                    │  - Time-range queries  │
                    │  - Aggregations        │
                    │  - Top-N queries       │
                    │  - Correlation helpers │
                    └────────────────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │   Gemini 3 Agent       │
                    │  - Autonomous Analysis │
                    │  - Root Cause Diag     │
                    │  - Action Planning     │
                    └────────────────────────┘
```

## Database Schema

### Design Principles

1. **Separate Tables per Metric Type**: Each metric type has its own table for:
   - Type-safe storage
   - Independent indexing strategies
   - Easy schema evolution
   - Efficient space usage

2. **Strategic Indexes**: Indexes on:
   - Timestamps (for time-range queries)
   - Process IDs (for process-centric analysis)
   - Metric values (for top-N queries)
   - Composite indexes for common query patterns

3. **Timestamp Resolution**: All timestamps stored as nanoseconds since epoch (INT64) for:
   - Microsecond precision
   - Easy comparison and math
   - Consistent across all tables

### Tables

#### eBPF Event Tables

**syscall_events**
- Tracks high-latency syscalls (>10ms threshold)
- Columns: timestamp, pid, tid, cpu, uid, syscall_nr, syscall_name, latency_ns, ret_value, is_error, arg0, comm
- Primary use: Identifying slow system calls that impact performance

**page_fault_events**
- Records page faults with resolution latency
- Columns: timestamp, pid, tid, cpu, address, latency_ns, fault_type, access_type, user_mode, comm
- Primary use: Memory pressure analysis and thrashing detection

**io_latency_stats**
- Aggregated I/O latency percentiles (1-second intervals)
- Columns: timestamp, read/write counts/bytes, p50/p95/p99/max latencies
- Primary use: Disk performance monitoring and anomaly detection

**sched_events**
- Scheduler latency events
- Columns: timestamp, pid, tid, cpu, latency_ns, prev_state, next_pid, comm
- Primary use: CPU scheduling analysis and starvation detection

#### System Metrics Tables

**memory_metrics**
- Memory statistics from /proc/meminfo
- Polling: Every 1 second
- Primary use: Memory pressure and OOM prediction

**load_metrics**
- System load averages
- Polling: Every 1 second
- Primary use: Overall system health indicator

**block_stats**
- Per-device block I/O statistics
- Polling: Every 1 second per device
- Primary use: Disk throughput and latency tracking

**network_interface_stats**
- Per-interface network statistics
- Polling: Every 1 second per interface
- Primary use: Network bandwidth and error tracking

**tcp_stats**
- TCP connection state counts
- Polling: Every 1 second
- Primary use: Connection leak and exhaustion detection

**tcp_retransmit_stats**
- TCP retransmission counters
- Polling: Every 1 second
- Primary use: Network quality issues

### Views

**v_recent_slow_syscalls**
- Last hour of high-latency syscalls, ordered by latency
- Fast access to recent performance issues

**v_memory_pressure**
- Memory usage percentage and swap utilization
- Quick health check view

**v_io_performance**
- I/O throughput and latency summary
- Dashboard-ready metrics

## Ingestion Daemon

### Configuration

```bash
python src/pipeline/ingestion_daemon.py \
  --db-path data/kernelsight.db \
  --batch-size 100 \
  --batch-timeout 1.0 \
  --verbose
```

Options:
- `--db-path`: Database file location
- `--batch-size`: Events to accumulate before commit (default: 100)
- `--batch-timeout`: Seconds before forcing commit (default: 1.0)
- `--init-only`: Initialize schema and exit
- `--verbose`: Enable debug logging

### Performance Characteristics

- **Throughput**: Tested at >1000 events/second
- **Latency**: <100ms for batch commit
- **Memory**: ~50MB baseline, scales with batch size
- **Disk**: ~100MB/day for typical workload

### Error Handling

The daemon handles errors gracefully:
- JSON parse errors: Logged and skipped
- Insert errors: Logged with event details
- Database errors: Logged, retry on next batch
- Shutdown signals: Commits pending events before exit

## Query Utilities

### Common Patterns

#### Time-Range Queries

```python
from datetime import datetime, timedelta
from db_manager import DatabaseManager
from query_utils import query_syscalls_by_timerange

db = DatabaseManager('data/kernelsight.db')
end = datetime.now()
start = end - timedelta(hours=1)

# Get slowest syscalls in last hour
syscalls = query_syscalls_by_timerange(db, start, end, min_latency_ms=50, limit=10)
for sc in syscalls:
    print(f"{sc['time']} | {sc['comm']} | {sc['syscall_name']}: {sc['latency_ms']}ms")
```

#### Top Processes by Metric

```python
from query_utils import query_top_processes_by_syscall_latency

# Find processes with slowest syscalls
top_procs = query_top_processes_by_syscall_latency(db, start, end, limit=5)
for proc in top_procs:
    print(f"{proc['comm']} (PID {proc['pid']}): {proc['avg_latency_ms']:.2f}ms avg")
```

#### I/O Performance

```python
from query_utils import query_io_latency_percentiles

io_stats = query_io_latency_percentiles(db, start, end)
for stat in io_stats:
    print(f"{stat['time']} | Read P95: {stat['read_p95_us']}us | "
          f"Write P95: {stat['write_p95_us']}us")
```

### Direct SQL Queries

The database can also be queried directly with SQL:

```sql
-- Find memory pressure events
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    (mem_total_kb - mem_available_kb) * 100.0 / mem_total_kb as used_pct,
    swap_total_kb - swap_free_kb as swap_used_kb
FROM memory_metrics
WHERE used_pct > 90 OR swap_used_kb > 1000000
ORDER BY timestamp DESC;

-- Correlate slow syscalls with memory pressure
SELECT 
    s.comm,
    s.syscall_name,
    AVG(s.latency_ns / 1000000.0) as avg_latency_ms,
    AVG(m.mem_available_kb) as avg_mem_available
FROM syscall_events s
JOIN memory_metrics m ON 
    abs(s.timestamp - m.timestamp) < 1000000000  -- within 1 second
WHERE s.timestamp > (strftime('%s', 'now') - 3600) * 1000000000
GROUP BY s.comm, s.syscall_name
HAVING avg_latency_ms > 20
ORDER BY avg_latency_ms DESC;
```

## Testing

### Unit Tests

```bash
python tests/test_pipeline.py
```

Covers:
- Event type identification
- JSON parsing
- Event normalization
- Database operations
- End-to-end pipeline

### Integration Tests

```bash
# Generate synthetic data
python tests/generate_test_data.py | \
  python src/pipeline/ingestion_daemon.py --db-path data/test.db

# Verify results
python tests/verify_database.py
```

### Manual Testing

```bash
# Initialize database
python src/pipeline/ingestion_daemon.py --init-only

# Pipe from real collectors (Linux/WSL)
./build/src/telemetry/scraper_daemon | \
  python src/pipeline/ingestion_daemon.py

# Query the data
python src/pipeline/query_utils.py --demo
```

## Performance Tuning

### Batch Size

- Smaller batches (10-50): Lower latency, more I/O overhead
- Larger batches (100-500): Higher throughput, more memory
- Recommended: 100 (good balance)

### Database Optimizations

The schema includes these optimizations:
- **WAL mode**: Better concurrent read/write
- **PRAGMA synchronous=NORMAL**: Faster commits
- **Large cache size**: 64MB cache for queries
- **Strategic indexes**: Only on frequently queried columns

### Data Retention

For long-term storage, implement retention policies:

```sql
-- Delete events older than 30 days
DELETE FROM syscall_events 
WHERE timestamp < (strftime('%s', 'now') - 30*24*3600) * 1000000000;

-- Or archive to separate database
ATTACH DATABASE 'archive.db' AS archive;
INSERT INTO archive.syscall_events 
SELECT * FROM syscall_events 
WHERE timestamp < (strftime('%s', 'now') - 7*24*3600) * 1000000000;
DELETE FROM syscall_events 
WHERE timestamp < (strftime('%s', 'now') - 7*24*3600) * 1000000000;
```

## Future Enhancements

1. **Downsampling**: Aggregate old data to reduce storage
2. **Partitioning**: Separate tables by time range
3. **Compression**: Use SQLite compression extensions
4. **Anomaly Tables**: Pre-computed anomaly detection results
5. **Correlation Views**: Multi-metric correlation materialized views
6. **Alternative Backends**: ClickHouse for larger deployments

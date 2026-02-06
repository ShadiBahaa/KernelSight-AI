# End-to-End Pipeline Testing Guide

This guide walks you through testing the complete KernelSight AI data pipeline with real telemetry data on a Linux VM.

## Prerequisites

### System Requirements
- Linux kernel 5.15+ with eBPF support
- Python 3.8+
- Root access (for eBPF tracers)
- SQLite 3.35+
- At least 1GB free disk space

### Built Components
Before running the test, ensure all collectors are built:

```bash
cd /path/to/KernelSight AI
mkdir build && cd build
cmake ..
make
```

Verify the following binaries exist:
- `build/src/telemetry/scraper_daemon`
- `build/src/telemetry/io_latency_tracer` (optional, requires root)
- `build/src/telemetry/syscall_tracer` (optional, requires root)

## Quick Test

### Automated Test Script

The easiest way to test is using the provided script:

```bash
# Run with default settings (60 seconds)
sudo ./scripts/test_pipeline_e2e.sh

# Run for a custom duration
TEST_DURATION=120 sudo ./scripts/test_pipeline_e2e.sh

# Use a custom database path
DB_PATH=/tmp/test.db ./scripts/test_pipeline_e2e.sh
```

**What the script does:**
1. Checks prerequisites and build status
2. Initializes a fresh database
3. Starts the ingestion daemon
4. Launches all available collectors
5. Runs for the specified duration
6. Stops collectors gracefully
7. Verifies data integrity
8. Displays statistics and sample queries

### Expected Output

```
╔════════════════════════════════════════════════════════════╗
║   KernelSight AI - End-to-End Pipeline Test               ║
║   Real Telemetry Data Collection & Ingestion              ║
╚════════════════════════════════════════════════════════════╝

=== Checking Prerequisites ===
✓ All prerequisites met

=== Initializing Database ===
  Creating database schema...
✓ Database initialized at data/pipeline_e2e_test.db

=== Starting Ingestion Daemon ===
  Ingestion daemon PID: 12345
  Log file: logs/pipeline_test/ingestion.log
✓ Ingestion daemon started

=== Starting Telemetry Collectors ===
  Starting scraper_daemon...
    PID: 12346 | Log: logs/pipeline_test/scraper.log
  Starting io_latency_tracer (requires root)...
    PID: 12347 | Log: logs/pipeline_test/io_tracer.log
  Starting syscall_tracer (requires root)...
    PID: 12348 | Log: logs/pipeline_test/syscall_tracer.log
✓ Collectors started

=== Running Test for 60s ===
  Elapsed: 60s / 60s
✓ Test duration complete

=== Verifying Results ===
Database Statistics:
table_name                row_count
------------------------  ----------
memory_metrics            60
load_metrics              60
network_interface_stats   180
block_stats               120
io_latency_stats          60
tcp_stats                 60
tcp_retransmit_stats      60
syscall_events            24
...
```

## Manual Testing

### Step 1: Initialize Database

```bash
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/test.db
```

### Step 2: Start Ingestion Daemon

In terminal 1:
```bash
python3 src/pipeline/ingestion_daemon.py \
  --db-path data/test.db \
  --batch-size 50 \
  --batch-timeout 1.0 \
  --verbose
```

The daemon will wait for JSON input on stdin.

### Step 3: Start Collectors

In terminal 2, pipe collectors to the daemon:

**Scraper daemon only (no root required):**
```bash
./build/src/telemetry/scraper_daemon | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/test.db
```

**With eBPF tracers (requires root):**
```bash
# Create a named pipe for multiple collectors
mkfifo /tmp/kernelsight_pipe

# Start ingestion reading from pipe
python3 src/pipeline/ingestion_daemon.py --db-path data/test.db < /tmp/kernelsight_pipe &

# Start collectors writing to pipe
./build/src/telemetry/scraper_daemon >> /tmp/kernelsight_pipe 2>&1 &
sudo ./build/src/telemetry/io_latency_tracer >> /tmp/kernelsight_pipe 2>&1 &
sudo ./build/src/telemetry/syscall_tracer >> /tmp/kernelsight_pipe 2>&1 &
```

### Step 4: Generate System Load (Optional)

To generate interesting telemetry data:

```bash
# Generate I/O load
dd if=/dev/zero of=/tmp/test bs=1M count=1000

# Generate syscall load
find /usr -type f | xargs cat > /dev/null 2>&1

# Generate network load
curl -O https://www.kernel.org/pub/linux/kernel/v5.x/linux-5.15.tar.xz
```

### Step 5: Monitor Progress

In terminal 3, monitor the ingestion:

```bash
# Watch ingestion log
tail -f logs/pipeline_test/ingestion.log

# Check database size
watch -n 5 'ls -lh data/test.db*'

# Query live data
watch -n 10 'sqlite3 data/test.db "SELECT COUNT(*) FROM memory_metrics"'
```

### Step 6: Stop and Verify

```bash
# Stop collectors (Ctrl+C in their terminals)
# The ingestion daemon will flush remaining events

# Verify data
python3 tests/verify_database.py

# Run query demos
python3 src/pipeline/query_utils.py --db-path data/test.db --demo
```

## Verification Checklist

After running the test, verify:

- [ ] **Database Created**: `data/test.db` exists and is >100KB
- [ ] **Multiple Tables Populated**: At least 5 tables have data
- [ ] **No Parse Errors**: Check ingestion log for parse_errors: 0
- [ ] **No Insert Errors**: Check ingestion log for insert_errors: 0
- [ ] **Timestamps Reasonable**: Query shows recent timestamps
- [ ] **Collectors Ran**: Log files exist for all collectors
- [ ] **Queries Work**: Demo queries return results

## Common Issues

### Issue: "Permission denied" for eBPF tracers

**Solution**: Run with sudo
```bash
sudo ./scripts/test_pipeline_e2e.sh
```

### Issue: "vmlinux.h not found"

**Solution**: Ensure BTF is available
```bash
# Check if BTF is available
ls /sys/kernel/btf/vmlinux

# If missing, you may need to install linux-headers
sudo apt-get install linux-headers-$(uname -r)
```

### Issue: No data in database

**Check**:
1. Are collectors running? `ps aux | grep -E 'scraper|tracer'`
2. Are they outputting JSON? `./build/src/telemetry/scraper_daemon | head -5`
3. Is ingestion daemon receiving data? Check logs
4. Are there parse errors? Grep ingestion log for "ERROR"

### Issue: High CPU usage

**Tuning**:
```bash
# Reduce batch frequency
python3 src/pipeline/ingestion_daemon.py \
  --batch-size 200 \
  --batch-timeout 5.0
```

### Issue: Database too large

**Implement retention**:
```sql
-- Delete events older than 1 hour
DELETE FROM syscall_events 
WHERE timestamp < (strftime('%s', 'now') - 3600) * 1000000000;

-- Vacuum to reclaim space
VACUUM;
```

## Performance Expectations

Based on testing, you should see:

| Metric | Expected Value |
|--------|---------------|
| Ingestion rate | 500-2000 events/sec |
| Database growth | 50-200 MB/hour |
| CPU usage (ingestion) | 5-15% |
| Memory usage | 50-100 MB |
| Batch commit latency | <50ms |

## Sample Queries

After data collection, try these queries:

### View Recent Memory Pressure
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    (mem_total_kb - mem_available_kb) * 100.0 / mem_total_kb as used_pct,
    swap_total_kb - swap_free_kb as swap_used_kb
FROM memory_metrics
WHERE timestamp > (strftime('%s', 'now') - 300) * 1000000000
ORDER BY timestamp DESC
LIMIT 10;
```

### Find Slow Syscalls
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    comm,
    syscall_name,
    latency_ns / 1000000.0 as latency_ms
FROM syscall_events
ORDER BY latency_ns DESC
LIMIT 10;
```

### I/O Performance Trend
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    read_count + write_count as total_ops,
    (read_bytes + write_bytes) / 1024.0 / 1024.0 as total_mb,
    read_p95_us,
    write_p95_us
FROM io_latency_stats
ORDER BY timestamp DESC
LIMIT 10;
```

## Next Steps

Once the pipeline test is successful:

1. **Run Longer Tests**: Try 24-hour runs to test stability
2. **Monitor Performance**: Track database growth and query latency
3. **Tune Parameters**: Adjust batch sizes for your workload
4. **Add Retention**: Implement data archival policies
5. **Integrate with Agent**: Connect Gemini 3 for autonomous analysis

## Troubleshooting Logs

All logs are stored in `logs/pipeline_test/`:
- `ingestion.log` - Ingestion daemon output
- `scraper.log` - Sysfs/procfs scraper output
- `io_tracer.log` - I/O latency tracer output
- `syscall_tracer.log` - Syscall tracer output

To debug issues, check these logs for errors or warnings.

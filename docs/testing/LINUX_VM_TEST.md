# Linux VM Pipeline Test - Step-by-Step Instructions

Follow these steps on your Linux VM to test the complete pipeline with real telemetry data.

## Prerequisites Check

```bash
# Verify you're on Linux
uname -s  # Should output: Linux

# Check kernel version (need 5.15+)
uname -r

# Check Python version (need 3.8+)
python3 --version

# Verify build directory exists
ls build/src/telemetry/scraper_daemon
```

## Recommended: Full System (Easiest)

The simplest way to run the complete system:

```bash
# Run the full system (auto-creates venv, installs deps, prompts for API key)
./start_kernelsight.sh
```

This opens 8 terminal windows - one for each component. See `docs/PRODUCTION_DEPLOYMENT.md` for details.

---

## Option 1: Quick Pipeline Test

For testing just the data pipeline (no agents):

```bash
# 1. Make the script executable
chmod +x scripts/debug/quick_pipeline_test.sh

# 2. Create logs directory
mkdir -p logs

# 3. Run the test
./scripts/debug/quick_pipeline_test.sh
```

**What you should see:**
- Database initialization
- Daemon starting
- Scraper collecting data for 30 seconds
- Summary showing events collected
- Instructions for querying data

**Expected output:**
```
KernelSight AI - Quick Pipeline Test
=====================================

[1/5] Initializing database...
✓ Database created

[2/5] Starting ingestion daemon...
✓ Daemon started (PID: 12345)

[3/5] Starting scraper_daemon...
✓ Scraper started (PID: 12346)

[4/5] Collecting data for 30 seconds...
  Progress: 30/30 seconds
✓ Collection complete

[5/5] Stopping collectors...
✓ Stopped

Results:
--------
Total events collected: 180

Events by table:
  load_metrics                       30 rows
  memory_metrics                     30 rows
  network_interface_stats            90 rows
  block_stats                        30 rows
```

## Option 2: Comprehensive Test with eBPF (Requires Root)

For a complete test including eBPF tracers:

```bash
# 1. Make script executable
chmod +x scripts/debug/test_pipeline_e2e.sh

# 2. Run with sudo (for eBPF tracers)
sudo ./scripts/debug/test_pipeline_e2e.sh

# Or run for a specific duration (e.g., 120 seconds)
sudo TEST_DURATION=120 ./scripts/debug/test_pipeline_e2e.sh
```

**This will test:**
- Scraper daemon (sysfs/procfs metrics)
- I/O latency tracer (eBPF)
- Syscall tracer (eBPF)
- Full ingestion pipeline
- Database queries

## Option 3: Manual Step-by-Step

For full control and troubleshooting:

### Terminal 1: Initialize and Start Ingestion

```bash
# Initialize database
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/manual_test.db

# Start ingestion daemon
python3 src/pipeline/ingestion_daemon.py \
  --db-path data/manual_test.db \
  --batch-size 50 \
  --verbose
```

Leave this running. You should see:
```
INFO - Database directory: /path/to/KernelSight AI/data
INFO - Connected to database: data/manual_test.db
INFO - Database schema initialized
INFO - Ingestion daemon started
INFO - Reading events from stdin...
```

### Terminal 2: Start Scraper

```bash
# Pipe scraper output to ingestion daemon
./build/src/telemetry/scraper_daemon | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/manual_test.db
```

You should see JSON events flowing and ingestion stats being logged.

### Terminal 3 (Optional): Start eBPF Tracers

```bash
# I/O latency tracer (requires root)
sudo ./build/src/telemetry/io_latency_tracer | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/manual_test.db &

# Syscall tracer (requires root)
sudo ./build/src/telemetry/syscall_tracer | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/manual_test.db &
```

### Terminal 4: Monitor in Real-Time

```bash
# Watch database size grow
watch -n 2 'ls -lh data/manual_test.db*'

# Query live data
watch -n 5 "python3 -c \"
import sys
sys.path.insert(0, 'src/pipeline')
from db_manager import DatabaseManager
db = DatabaseManager('data/manual_test.db')
stats = db.get_table_stats()
for table, count in sorted(stats.items()):
    if count > 0:
        print(f'{table:30} {count:6}')
db.close()
\""
```

## Verification Steps

After running for 30-60 seconds, verify the pipeline worked:

### 1. Check Database Exists
```bash
ls -lh data/*.db
```

Expected: File size >100KB

### 2. Check Table Counts
```bash
python3 tests/verify_database.py
```

Expected output showing multiple tables with data.

### 3. Run Query Demos
```bash
python3 src/pipeline/query_utils.py --db-path data/quicktest.db --demo
```

Expected: Sample queries showing recent data.

### 4. Check for Errors
```bash
# Check ingestion log
grep -i error logs/ingestion*.log

# Should see:
# Parse errors: 0
# Insert errors: 0
```

### 5. Direct SQL Queries
```bash
# Count total events
sqlite3 data/quicktest.db "
SELECT 
    'memory_metrics' as table_name, 
    COUNT(*) as count 
FROM memory_metrics
"

# View recent memory stats
sqlite3 data/quicktest.db "
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    mem_available_kb / 1024 as mem_available_mb
FROM memory_metrics
ORDER BY timestamp DESC
LIMIT 5
"
```

## Troubleshooting

### Problem: "Module 'db_manager' not found"

```bash
# Ensure you're in the project root
pwd  # Should be /path/to/KernelSight AI

# Set PYTHONPATH if needed
export PYTHONPATH=$PWD/src/pipeline:$PYTHONPATH
```

### Problem: "scraper_daemon not found"

```bash
# Rebuild the project
cd build
make
cd ..

# Verify binary exists
ls -l build/src/telemetry/scraper_daemon
```

### Problem: No data in database

```bash
# Test scraper output directly
./build/src/telemetry/scraper_daemon | head -20

# Should see JSON like:
# {"timestamp": 1234567890000000000, "mem_total_kb": 8192000, ...}

# Test event parser
echo '{"timestamp": 1234567890000000000, "mem_total_kb": 8192000, "mem_available_kb": 4096000}' | \
  python3 -c "
import sys
sys.path.insert(0, 'src/pipeline')
from event_parsers import parse_json_line
for line in sys.stdin:
    result = parse_json_line(line.strip())
    print(result)
"
```

### Problem: eBPF tracers fail

```bash
# Check if running as root
whoami  # Should be: root

# Check BTF support
ls /sys/kernel/btf/vmlinux

# If missing, install headers
sudo apt-get update
sudo apt-get install linux-headers-$(uname -r)

# Rebuild
cd build && cmake .. && make && cd ..
```

## Expected Performance

On a typical Linux VM, you should see:

- **Events/second**: 5-10 events/sec from scraper alone
- **Database growth**: ~10-50 MB/hour depending on collectors
- **CPU usage**: <5% for ingestion daemon
- **Memory usage**: ~50MB for ingestion daemon

## Success Criteria

✅ Your test is successful if:

1. Database file created and growing
2. Multiple tables have data (at least memory, load, network)
3. No parse or insert errors in logs
4. Queries return recent timestamps
5. Sample data looks reasonable (memory values make sense, etc.)

## Next Steps After Successful Test

1. **Run Production System**: Use the full GUI launcher
   ```bash
   ./start_kernelsight.sh
   ```

2. **Generate Load**: Create interesting events to capture
   ```bash
   # I/O stress
   dd if=/dev/zero of=/tmp/test bs=1M count=1000
   
   # CPU stress
   stress --cpu 4 --timeout 60
   ```

3. **Analyze Data**: Use SQL to find patterns
   ```bash
   sqlite3 data/quicktest.db
   ```

4. **Tune Performance**: Adjust batch sizes
   ```bash
   # Larger batches for higher throughput
   python3 src/pipeline/ingestion_daemon.py \
     --batch-size 200 \
     --batch-timeout 2.0
   ```

5. **Setup Continuous Collection**: Run as a service
   ```bash
   # Create systemd service (future work)
   ```

## Questions?

Check the comprehensive documentation:
- [docs/pipeline/DATA_PIPELINE.md](../pipeline/DATA_PIPELINE.md)
- [docs/testing/E2E_PIPELINE_TEST.md](E2E_PIPELINE_TEST.md)

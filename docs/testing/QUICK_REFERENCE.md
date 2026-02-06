# Pipeline Testing - Quick Reference Card

## Quick Start (30 seconds)
```bash
chmod +x scripts/quick_pipeline_test.sh && mkdir -p logs
./scripts/quick_pipeline_test.sh
```

## Full Test with eBPF (60 seconds, requires root)
```bash
chmod +x scripts/test_pipeline_e2e.sh
sudo ./scripts/test_pipeline_e2e.sh
```

## Manual Pipeline Setup

### Start Ingestion Daemon
```bash
python3 src/pipeline/ingestion_daemon.py --db-path data/test.db --verbose
```

### Start Scraper (in another terminal)
```bash
./build/src/telemetry/scraper_daemon | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/test.db
```

### Start eBPF Tracers (requires root)
```bash
sudo ./build/src/telemetry/io_latency_tracer | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/test.db &
  
sudo ./build/src/telemetry/syscall_tracer | \
  python3 src/pipeline/ingestion_daemon.py --db-path data/test.db &
```

## Verification Commands

### Check Database
```bash
ls -lh data/*.db
sqlite3 data/test.db "SELECT COUNT(*) FROM memory_metrics;"
```

### View Table Stats
```bash
python3 tests/verify_database.py
```

### Run Query Demos
```bash
python3 src/pipeline/query_utils.py --db-path data/test.db --demo
```

### Monitor in Real-Time
```bash
# Watch database grow
watch -n 5 'ls -lh data/test.db*'

# Watch event counts
watch -n 5 'sqlite3 data/test.db "SELECT COUNT(*) FROM memory_metrics"'
```

## Common SQL Queries

### Recent Memory Usage
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    mem_available_kb / 1024 as mem_avail_mb,
    (mem_total_kb - mem_available_kb) * 100.0 / mem_total_kb as used_pct
FROM memory_metrics
ORDER BY timestamp DESC
LIMIT 10;
```

### Slow Syscalls
```sql
SELECT 
    comm, syscall_name, 
    latency_ns / 1000000.0 as latency_ms
FROM syscall_events
ORDER BY latency_ns DESC
LIMIT 10;
```

### I/O Performance
```sql
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    read_count, write_count,
    read_p95_us, write_p95_us
FROM io_latency_stats
ORDER BY timestamp DESC
LIMIT 10;
```

## Troubleshooting

### Binary not found
```bash
cd build && make && cd ..
```

### No data appearing
```bash
# Test scraper output
./build/src/telemetry/scraper_daemon | head -5

# Check logs
tail -f logs/ingestion*.log
```

### eBPF errors
```bash
# Install headers
sudo apt-get install linux-headers-$(uname -r)

# Rebuild
cd build && cmake .. && make && cd ..
```

## File Locations

- **Database**: `data/test.db`
- **Logs**: `logs/`
- **Scripts**: `scripts/`
- **Tests**: `tests/`

## Expected Results (30 sec test)

- **Events**: 150-300 total
- **Memory metrics**: ~30 rows
- **Network stats**: ~90 rows
- **DB size**: 100-500 KB
- **Parse errors**: 0
- **Insert errors**: 0

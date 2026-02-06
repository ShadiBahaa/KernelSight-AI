# Running a 1-Hour Pipeline Test

This guide explains how to run KernelSight AI for 1 hour to collect production-scale telemetry data.

---

## Quick Start

### Option 1: Using Existing Script (Recommended)

The `stress_test_full.sh` script already supports custom durations:

```bash
# Run for 1 hour (3600 seconds)
sudo TEST_DURATION=3600 ./scripts/stress_test_full.sh
```

### Option 2: Using Dedicated Helper Script

For convenience, use the provided helper:

```bash
sudo ./scripts/run_1hour_test.sh
```

---

## What Happens During the Test

### Data Collection (Entire Duration)

**eBPF Tracers** (running continuously):
- `syscall_tracer` - Captures system call events
- `io_latency_tracer` - Tracks I/O latency statistics
- `page_fault_tracer` - Monitors page fault events
- `sched_tracer` - Records scheduler activity

**Scraper Daemon** (polling every 1 second):
- Memory metrics from `/proc/meminfo`
- Load averages from `/proc/loadavg`
- Block device stats from `/sys/block/*/stat`
- Network interface stats from `/proc/net/dev`
- TCP connection states from `/proc/net/tcp`

**Ingestion Daemon**:
- Reads all events from FIFO pipe
- Batch inserts into SQLite database
- Commits every 100 events or 1 second

### System Stress (First 60 seconds)

> [!NOTE]
> By default, the stress workload only runs for 60 seconds, not the full hour. This is intentional to capture both stressed and normal system behavior.

**Workloads** (if `stress` tool is installed):
- CPU stress: 4 workers
- Memory stress: 2 workers × 512MB
- I/O stress: 4 workers

**Additional workloads**:
- Heavy disk I/O (dd operations)
- File system operations (find + read)
- Network stress (HTTP server + clients)
- TCP connection bursts

### Post-Stress Collection (Remaining ~59 minutes)

After the stress workload completes, the collectors continue running to capture:
- System recovery patterns
- Baseline "normal" behavior
- Long-term trends
- Idle system characteristics

This is valuable for **baseline learning** and **anomaly detection**.

---

## Expected Database Size

Based on previous tests:

| Duration | Approximate Size | Event Count (estimated) |
|----------|------------------|------------------------|
| 1 minute | ~250 KB | 1,000-3,000 |
| 5 minutes | ~1 MB | 5,000-15,000 |
| 10 minutes | ~2 MB | 10,000-30,000 |
| **1 hour** | **~10-15 MB** | **~60,000-180,000** |

**Note**: Size varies based on system activity. More events = larger database.

---

## Monitoring Progress

### During the Test

The script displays:
- Initialization progress (1/6 through 6/6)
- Real-time progress bar
- Elapsed time vs. total duration

```
Progress: [===================                                ] 1200/3600s
```

### Checking Logs (in another terminal)

```bash
# Watch ingestion progress
tail -f logs/stress_test/ingestion.log

# Monitor scraper
tail -f logs/stress_test/scraper.log

# Check syscall tracer
tail -f logs/stress_test/syscall.log
```

### Querying Database (in another terminal)

```bash
# Install sqlite3 if needed (WSL)
sudo apt-get install sqlite3

# Count total events
sqlite3 data/stress_test.db "SELECT SUM(cnt) FROM (
    SELECT COUNT(*) as cnt FROM syscall_events
    UNION ALL SELECT COUNT(*) FROM page_fault_events
    UNION ALL SELECT COUNT(*) FROM memory_metrics
);"

# Show events per table
python3 -c "
import sys
sys.path.insert(0, 'src/pipeline')
from db_manager import DatabaseManager
db = DatabaseManager('data/stress_test.db')
stats = db.get_table_stats()
for table, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
    print(f'{table:30} {count:8,} rows')
db.close()
"
```

---

## After the Test Completes

### Automatic Summary

The script automatically displays:
- Total events collected
- Event type breakdown
- Sample data (slow syscalls, page faults)

### Manual Analysis

#### 1. Run Exploratory Data Analysis

```bash
python scripts/explore_data.py \
    --database data/stress_test.db \
    --output-dir data/reports/1hour_test \
    --log-dir logs/stress_test
```

This generates:
- 11 visualization plots
- Database overview report
- Log analysis report

#### 2. Feature Engineering

```bash
# Extract features for entire dataset
python scripts/verify_features.py --db-path data/stress_test.db
```

#### 3. Baseline Learning

```bash
# Learn baseline from normal period (last 30 minutes)
python -c "
import sys
sys.path.insert(0, 'src/pipeline/features')
from feature_engine import FeatureEngine
from exporter import FeatureExporter

engine = FeatureEngine('data/stress_test.db')

# Use last 30 minutes as baseline (normal behavior)
# Calculate start time: get max timestamp and subtract 1800 seconds
import sqlite3
conn = sqlite3.connect('data/stress_test.db')
max_ts = conn.execute('SELECT MAX(timestamp) FROM memory_metrics').fetchone()[0]
conn.close()

baseline_start = max_ts - 1800 if max_ts else None

if baseline_start:
    features = engine.compute_features(window_size=1800, baseline_mode=True)
    baseline = engine.baseline_stats
    
    # Export baseline
    exporter = FeatureExporter('data/features')
    exporter.export_json(features, baseline, '1hour_baseline_metadata.json')
    
    print(f'Baseline learned from {len(features.get(\"timestamp\", []))} samples')
    print(f'Baseline saved to data/features/1hour_baseline_metadata.json')
else:
    print('Not enough data for baseline learning')
"
```

---

## Customization Options

### Change Test Duration

```bash
# 30 minutes
sudo TEST_DURATION=1800 ./scripts/stress_test_full.sh

# 2 hours
sudo TEST_DURATION=7200 ./scripts/stress_test_full.sh

# 24 hours (for long-term baseline)
sudo TEST_DURATION=86400 ./scripts/stress_test_full.sh
```

### Change Output Location

Edit the script or set environment variables:

```bash
sudo DB_PATH="data/production_test.db" \
     LOG_DIR="logs/production_test" \
     TEST_DURATION=3600 \
     ./scripts/stress_test_full.sh
```

### Disable Stress Workload

If you want to collect **only baseline data** without stress:

1. Open `scripts/stress_test_full.sh`
2. Comment out lines 173-254 (the stress generation section)
3. Run normally

Or create a minimal collection script (see `run_baseline_collection.sh` below).

---

## Running Multiple Tests

### Sequential Tests

```bash
# Test 1: With stress
sudo TEST_DURATION=3600 ./scripts/stress_test_full.sh
mv data/stress_test.db data/test1_stressed.db

# Test 2: Baseline only (no stress)
# ... (disable stress workload first)
sudo TEST_DURATION=3600 ./scripts/stress_test_full.sh
mv data/stress_test.db data/test2_baseline.db
```

### Parallel Tests (Not Recommended)

> [!WARNING]
> Running multiple tests simultaneously is **not recommended** as they will:
> - Compete for the same FIFO pipe
> - Interfere with each other's measurements
> - Corrupt the database

---

## Troubleshooting

### Issue: "Permission denied" or "eBPF program failed to load"

**Solution**: Run with `sudo`:
```bash
sudo ./scripts/stress_test_full.sh
```

### Issue: "stress: command not found"

**Solution**: Install stress tool (optional):
```bash
sudo apt-get install stress
```

The script will continue without the stress workload if not installed.

### Issue: Database is locked

**Solution**: Only one ingestion process can write at a time. Make sure no other instances are running:
```bash
pkill -f ingestion_daemon
```

### Issue: Disk space running out

**Solution**: Monitor disk space:
```bash
df -h data/

# Stop test early if needed (Ctrl+C)
# Database will be in consistent state due to WAL mode
```

### Issue: Out of memory

**Solution**: The collectors are lightweight, but if running on a small VM:
- Reduce batch size in ingestion daemon
- Disable some eBPF tracers
- Run for shorter duration

---

## Performance Tips

### For Maximum Throughput

1. **Use SSD for database storage**
2. **Increase batch size**: Edit `stress_test_full.sh` line 93:
   ```bash
   --batch-size 1000  # Increased from 100
   ```
3. **Reduce log verbosity**: Remove `--verbose` flag

### For Minimal Overhead

1. **Disable syscall tracer** (highest event rate)
2. **Increase scraper interval**: Edit `scraper_daemon.cpp`
3. **Reduce batch timeout**: May decrease latency but increase overhead

---

## Next Steps After 1-Hour Test

1. **Analyze Results**:
   - Run `explore_data.py` for visualizations
   - Review log files for errors
   - Check database integrity

2. **Feature Engineering**:
   - Extract features with `verify_features.py`
   - Learn baseline from normal period
   - Export to NumPy for ML training

3. **Anomaly Detection**:
   - Run `test_anomaly_detection.py` on the data
   - Compare stressed vs. baseline periods
   - Tune z-score thresholds

4. **Documentation**:
   - Document any issues encountered
   - Note interesting patterns in data
   - Update baseline statistics

---

## Example: Complete 1-Hour Test Workflow

```bash
# Step 1: Run 1-hour test
sudo TEST_DURATION=3600 ./scripts/stress_test_full.sh

# Step 2: Analyze results
python scripts/explore_data.py \
    --database data/stress_test.db \
    --output-dir data/reports/1hour_$(date +%Y%m%d_%H%M%S)

# Step 3: Extract features
python scripts/verify_features.py --db-path data/stress_test.db

# Step 4: Learn baseline (last 30 min = normal behavior)
# ... (use baseline learning code above)

# Step 5: Backup results
tar -czf kernelsight_1hour_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/stress_test.db \
    data/features/ \
    data/reports/ \
    logs/stress_test/

# Step 6: Archive and start fresh
mv data/stress_test.db data/archived/stress_test_$(date +%Y%m%d_%H%M%S).db
```

---

## FAQ

**Q: Can I stop the test early?**  
A: Yes, press `Ctrl+C`. The database will be in a consistent state due to SQLite's WAL mode and the ingestion daemon's batch commits.

**Q: How much data will I collect?**  
A: Approximately 60,000-180,000 events in a 10-15 MB database, depending on system activity.

**Q: Can I run this on a production system?**  
A: The collectors have minimal overhead (<5% CPU), but the **stress workload** is not recommended for production. Consider disabling it or running during maintenance windows.

**Q: What if I want 24/7 monitoring?**  
A: For continuous monitoring, consider:
- Running as a systemd service
- Implementing log rotation
- Setting up database archival
- Using time-series databases (InfluxDB) for long-term storage

**Q: How long does analysis take?**  
A: `explore_data.py` processes a 1-hour database in ~10-15 seconds on a modern system.

---

## Resources

- [Stress Test Script](file:///c:/KernelSight%20AI/scripts/stress_test_full.sh)
- [1-Hour Helper Script](file:///c:/KernelSight%20AI/scripts/run_1hour_test.sh)
- [Baseline Collection Script](file:///c:/KernelSight%20AI/scripts/run_baseline_collection.sh)
- [EDA Script](file:///c:/KernelSight%20AI/scripts/explore_data.py)
- [Architecture Documentation](file:///c:/KernelSight%20AI/docs/architecture_diagram.md)

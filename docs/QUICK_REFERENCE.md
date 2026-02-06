# Quick Reference: Running Pipeline Tests

Quick commands for running KernelSight AI pipeline tests.

---

## 1-Hour Test (With Stress)

**Recommended for**: Initial testing, anomaly detection training

```bash
# Easy way (using helper script)
sudo ./scripts/run_1hour_test.sh

# Direct way (using environment variable)
sudo TEST_DURATION=3600 ./scripts/stress_test_full.sh
```

**What it does**:
- Runs stress workload for 1 minute (CPU, memory, I/O, network)
- Collects telemetry for the full hour
- Captures both stressed and normal behavior

**Expected output**: ~60,000-180,000 events in `data/stress_test.db` (~10-15 MB)

---

## Baseline Collection (No Stress)

**Recommended for**: Learning normal behavior, production monitoring

```bash
# 1 hour of baseline data
sudo ./scripts/run_baseline_collection.sh

# 30 minutes
sudo ./scripts/run_baseline_collection.sh 1800

# 2 hours
sudo ./scripts/run_baseline_collection.sh 7200
```

**What it does**:
- Runs collectors without any stress workload
- Captures normal system operation
- Ideal for baseline learning

**Expected output**: ~30,000-90,000 events in `data/baseline.db` (~5-8 MB)

---

## Quick Test (1 Minute)

**Recommended for**: Smoke testing, development

```bash
# Default 60-second test
sudo ./scripts/stress_test_full.sh
```

**Expected output**: ~1,000-3,000 events (~250 KB)

---

## Custom Duration

```bash
# 5 minutes
sudo TEST_DURATION=300 ./scripts/stress_test_full.sh

# 30 minutes
sudo TEST_DURATION=1800 ./scripts/stress_test_full.sh

# 24 hours (for long-term baseline)
sudo TEST_DURATION=86400 ./scripts/stress_test_full.sh
```

---

## Post-Test Analysis

### 1. Exploratory Data Analysis

```bash
# Analyze stress test
python scripts/explore_data.py \
    --database data/stress_test.db \
    --output-dir data/reports/1hour_test

# Analyze baseline
python scripts/explore_data.py \
    --database data/baseline.db \
    --output-dir data/reports/baseline
```

**Output**: 13 visualization files + 2 text reports

### 2. Feature Extraction

```bash
# Extract features from stress test
python scripts/verify_features.py --db-path data/stress_test.db

# Learn baseline from normal period
python scripts/verify_features.py --db-path data/baseline.db --baseline-mode
```

### 3. Anomaly Detection

```bash
# Run anomaly detection test
python scripts/test_anomaly_detection.py
```

---

## Monitoring During Test

### Watch logs in real-time

```bash
# Ingestion progress
tail -f logs/stress_test/ingestion.log

# Scraper activity
tail -f logs/stress_test/scraper.log

# eBPF tracers
tail -f logs/stress_test/syscall.log
```

### Query database live

```bash
# Count events (install sqlite3 if needed)
watch -n 5 'sqlite3 data/stress_test.db "SELECT COUNT(*) FROM syscall_events"'

# Or use Python
watch -n 5 'python -c "
import sys; sys.path.insert(0, \"src/pipeline\")
from db_manager import DatabaseManager
db = DatabaseManager(\"data/stress_test.db\")
stats = db.get_table_stats()
total = sum(v for v in stats.values() if v > 0)
print(f\"Total: {total:,} events\")
db.close()
"'
```

---

## Troubleshooting

### Permission denied
```bash
# Always use sudo for eBPF tracers
sudo ./scripts/run_1hour_test.sh
```

### stress: command not found
```bash
# Install stress tool (optional)
sudo apt-get install stress

# Or run without it (script will skip stress workload)
```

### Out of disk space
```bash
# Check space before running
df -h data/

# Clean old databases
rm data/*.db data/*.db-shm data/*.db-wal
```

### Stop test early
```bash
# Press Ctrl+C
# Database will be in consistent state (SQLite WAL mode)
```

---

## Complete Workflow Example

```bash
# 1. Run 1-hour test
sudo ./scripts/run_1hour_test.sh

# 2. Analyze results
python scripts/explore_data.py \
    --database data/stress_test.db \
    --output-dir data/reports/test_$(date +%Y%m%d_%H%M%S)

# 3. Extract features and learn baseline
python scripts/verify_features.py --db-path data/stress_test.db

# 4. Backup results
tar -czf kernelsight_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/stress_test.db \
    data/features/ \
    data/reports/ \
    logs/stress_test/

# 5. Archive and clean up
mkdir -p data/archived
mv data/stress_test.db data/archived/test_$(date +%Y%m%d_%H%M%S).db
```

---

## Files Created

| Script | Purpose |
|--------|---------|
| [run_1hour_test.sh](file:///c:/KernelSight%20AI/scripts/run_1hour_test.sh) | 1-hour test with stress |
| [run_baseline_collection.sh](file:///c:/KernelSight%20AI/scripts/run_baseline_collection.sh) | Baseline collection (no stress) |
| [stress_test_full.sh](file:///c:/KernelSight%20AI/scripts/stress_test_full.sh) | Core test script (configurable) |

| Documentation | Content |
|---------------|---------|
| [1HOUR_TEST_GUIDE.md](file:///c:/KernelSight%20AI/docs/1HOUR_TEST_GUIDE.md) | Comprehensive guide |
| [QUICK_REFERENCE.md](file:///c:/KernelSight%20AI/docs/QUICK_REFERENCE.md) | This file |

---

## Need Help?

See full documentation: [docs/1HOUR_TEST_GUIDE.md](file:///c:/KernelSight%20AI/docs/1HOUR_TEST_GUIDE.md)

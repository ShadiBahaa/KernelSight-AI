# Pipeline Troubleshooting Guide

## Problem: No Data in Database After E2E Test

If you ran the test and found no data in the database, follow these steps:

### Step 1: Run Diagnostics

```bash
chmod +x scripts/diagnose_pipeline.sh
./scripts/diagnose_pipeline.sh data/pipeline_e2e_test.db
```

This will:
- Check if database exists
- Count rows in all tables
- Test scraper output
- Test event parser
- Test database insertion
- Check log files for errors

### Step 2: Try the Simple Test

Use the simplified test which is more reliable:

```bash
chmod +x scripts/simple_pipeline_test.sh
./scripts/simple_pipeline_test.sh 30
```

This version:
- Collects events to a temp file first
- Then ingests them separately
- Avoids complex pipe redirection issues

### Step 3: Manual Test (Most Reliable)

If the simple test still fails, do a manual test:

**Terminal 1:**
```bash
# Just run the scraper and save to file
./build/src/telemetry/scraper_daemon > /tmp/events.json 2>&1
```

Let it run for 10-30 seconds, then **Ctrl+C**.

**Check the file:**
```bash
# Should see JSON events
head -5 /tmp/events.json

# Count lines
wc -l /tmp/events.json
```

Expected output: JSON objects like:
```json
{"timestamp": 1735829234000000000, "mem_total_kb": 8192000, ...}
```

**Terminal 2:**
```bash
# Initialize database
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/manual_test.db

# Ingest the collected events
cat /tmp/events.json | python3 src/pipeline/ingestion_daemon.py --db-path data/manual_test.db
```

You should see output like:
```
INFO - Ingestion daemon started
INFO - Total events processed: 150
INFO - Parse errors: 0
INFO - Insert errors: 0
```

**Verify:**
```bash
sqlite3 data/manual_test.db "SELECT COUNT(*) FROM memory_metrics"
```

Should show a number > 0.

## Common Issues and Fixes

### Issue 1: Scraper Not Outputting Data

**Symptoms:** Empty /tmp/events.json or no output when running scraper

**Fix:**
```bash
# Rebuild the scraper
cd build
make clean
cmake ..
make
cd ..

# Test again
./build/src/telemetry/scraper_daemon | head -5
```

### Issue 2: Parse Errors

**Symptoms:** Logs show "Parse errors: 50" or similar

**Check:**
```bash
# Run a single event through parser
echo '{"timestamp": 1234567890000000000, "mem_total_kb": 8192000, "mem_available_kb": 4096000}' | \
python3 -c "
import sys
sys.path.insert(0, 'src/pipeline')
from event_parsers import parse_json_line
result = parse_json_line(sys.stdin.read())
print(result)
"
```

**Fix:** If parser fails, check Python path:
```bash
export PYTHONPATH=$PWD/src/pipeline:$PYTHONPATH
```

### Issue 3: Database Permission Issues

**Symptoms:** "Permission denied" or "unable to open database"

**Fix:**
```bash
# Create data directory with proper permissions
mkdir -p data
chmod 755 data

# Remove and recreate database
rm -f data/*.db*
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/test.db
```

### Issue 4: Named Pipe Issues (Complex Scripts)

**Symptoms:** Script hangs or no data appears

**Fix:** Use the simple test instead:
```bash
./scripts/simple_pipeline_test.sh
```

The simple test avoids named pipes completely.

### Issue 5: Events Not Matching Schema

**Symptoms:** Insert errors in logs

**Check logs:**
```bash
grep "Insert errors" logs/pipeline_test/ingestion.log
grep -A 5 "ERROR" logs/pipeline_test/ingestion.log
```

**Fix:** Events might be from wrong collector version. Rebuild:
```bash
cd build && make clean && cmake .. && make && cd ..
```

## Verification Checklist

After fixing, verify these:

```bash
# 1. Database exists and has size
ls -lh data/*.db

# 2. Tables have data
sqlite3 data/test.db "SELECT name FROM sqlite_master WHERE type='table'"

# 3. Count rows
sqlite3 data/test.db "SELECT COUNT(*) FROM memory_metrics"

# 4. View sample data
sqlite3 data/test.db "SELECT * FROM memory_metrics LIMIT 1"

# 5. Check timestamps are recent
sqlite3 data/test.db "SELECT datetime(timestamp/1000000000, 'unixepoch') FROM memory_metrics LIMIT 1"
```

## Still Not Working?

Try the absolute minimal test:

```bash
# Create database
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/minimal.db

# Insert one event manually
python3 -c "
import sys
sys.path.insert(0, 'src/pipeline')
from db_manager import DatabaseManager
import time

db = DatabaseManager('data/minimal.db')
event = {
    'timestamp': int(time.time() * 1_000_000_000),
    'mem_total_kb': 8192000,
    'mem_free_kb': 4096000,
    'mem_available_kb': 6144000,
    'buffers_kb': 512000,
    'cached_kb': 2048000,
    'swap_total_kb': 4096000,
    'swap_free_kb': 4096000,
    'active_kb': 2048000,
    'inactive_kb': 1024000,
    'dirty_kb': 10240,
    'writeback_kb': 0
}
db.insert_memory_metrics(event)
db.commit()
print('Inserted 1 event')
db.close()
"

# Verify
sqlite3 data/minimal.db "SELECT COUNT(*) FROM memory_metrics"
```

If this works (shows "1"), then:
- ✓ Database is working
- ✓ Python environment is correct
- ⚠ Issue is with the pipeline/collector integration

If this doesn't work:
- Check Python version: `python3 --version` (need 3.8+)
- Check SQLite: `sqlite3 --version` (need 3.35+)
- Check file permissions in data/ directory

## Get Help

If you're still stuck, gather this info:

```bash
# System info
uname -a
python3 --version
sqlite3 --version

# File status
ls -la data/
ls -la build/src/telemetry/

# Run diagnostic
./scripts/diagnose_pipeline.sh data/test.db > diagnostic_output.txt 2>&1

# Check logs
tail -50 logs/pipeline_test/ingestion.log > ingestion_log.txt
```

Share these files for debugging assistance.

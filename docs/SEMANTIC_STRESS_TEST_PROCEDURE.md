# Semantic Stress Test Procedure

## Prerequisites

### 1. Environment
- **WSL 2** on Windows 11 with Ubuntu 22.04+
- **Kernel**: 5.15+ with BTF support
- **Root access**: eBPF tracers require root privileges

### 2. Dependencies
```bash
# Install if not already present
sudo apt-get update
sudo apt-get install -y stress jq sqlite3
```

### 3. Build Status
All eBPF programs must be compiled:
```bash
ls build/src/telemetry/
# Should show:
# - syscall_tracer
# - sched_tracer  
# - io_latency_tracer
# - page_fault_tracer
# - scraper_daemon
```

If not built:
```bash
cd build
cmake ..
make -j$(nproc)
cd ..
```

---

## Running the Test

### Option 1: Full 1-Hour Test (Recommended)

```bash
# Navigate to project in WSL
cd /mnt/c/KernelSight\ AI/

# Run 1-hour test (requires root)
sudo ./scripts/semantic_stress_test.sh
```

**Expected Duration**: ~60 minutes  
**Output**: Progress updates every minute

### Option 2: Quick 5-Minute Test

```bash
# Short test for validation
sudo TEST_DURATION=300 ./scripts/semantic_stress_test.sh
```

**Expected Duration**: 5 minutes  
**Purpose**: Verify everything works before long run

### Option 3: Background 1-Hour Test

```bash
# Run in background with nohup
sudo nohup ./scripts/semantic_stress_test.sh > test_output.log 2>&1 &

# Monitor progress
tail -f test_output.log

# Check if still running
pgrep -f semantic_stress_test
```

---

## What Happens During the Test

### Phase 1: Initialization (10 seconds)
```
[1/5] Initializing Semantic Database
  ✓ Creates data/semantic_stress_test.db
  ✓ Initializes schema v2 with signal_metadata table

[2/5] Starting Semantic Ingestion Daemon
  ✓ Loads all 4 classifiers (syscall, scheduler, system, pagefault)
  ✓ Opens FIFO for event stream
```

### Phase 2: Collector Startup (10 seconds)
```
[3/5] Starting eBPF Collectors + Scrapers
  ✓ syscall_tracer (captures >10ms syscalls)
  ✓ scraper_daemon (memory, load, network, TCP every second)
  ✓ (sched_tracer if available)
  ✓ (page_fault_tracer if available)
```

### Phase 3: Stress Workload (Duration)
```
[4/5] Starting System Stress Workload
  ✓ CPU stress (2 workers)
  ✓ Memory stress (512MB)
  ✓ I/O stress (2 workers)
```

### Phase 4: Monitoring (Duration)
```
[5/5] Running Test
  [1 min] Test in progress... (3540 seconds remaining)
    Raw events: 120 | Semantic signals: 8
  [2 min] Test in progress... (3480 seconds remaining)
    Raw events: 245 | Semantic signals: 15
  ...
```

### Phase 5: Cleanup & Report
```
✓ Test completed!

═══════════════════ Final Statistics ═══════════════════

Raw Event Counts:
Syscall Events: 150
Memory Metrics: 3600
Load Metrics: 3600
Network Stats: 3600
TCP Stats: 3600
...

Semantic Signal Counts:
syscall: 45
memory: 12
load: 8
io: 15
tcp: 3

Severity Distribution:
critical: 2
high: 18
medium: 35
low: 13

Sample Observations (Top 5 Critical/High):
time                | signal_type | severity | summary
2026-01-04 19:30:15 | memory      | critical | Memory pressure: Only 5% available
2026-01-04 19:32:20 | syscall     | high     | I/O bottleneck: stress blocked for 125ms
...
```

---

## Expected Results

### After 1 Hour

**Raw Events** (approx):
- Syscall events: ~100-200 (only high-latency >10ms)
- Memory metrics: 3,600 (1/sec)
- Load metrics: 3,600 (1/sec)
- Network stats: 3,600 (1/sec)
- TCP stats: 3,600 (1/sec)
- I/O stats: ~3,600 (1/sec)
- Block stats: ~7,200 (2/sec for 2 devices)
- **Total raw events**: ~20,000-25,000

**Semantic Signals** (approx):
- Syscall signals: ~50-100 (behavioral anomalies)
- Scheduler signals: ~10-30 (thrashing, contention)
- Memory pressure: ~20-40 (low memory events)
- I/O congestion: ~15-30 (queue saturation)
- Network degradation: ~5-10 (errors if any)
- TCP issues: ~5-15 (connection states)
- **Total semantic signals**: ~100-200 (only meaningful observations)

**Compression ratio**: ~0.5% (200 signals from 25,000 events)

### Signal Distribution

**By Severity**:
- Critical: 5-10 (swap thrashing, memory OOM risk)
- High: 20-40 (I/O bottlenecks, major faults)
- Medium: 40-80 (elevated pressure, busy patterns)
- Low: 30-60 (cold starts, normal variance)

**By Type**:
- `syscall` (blocking_io, lock_contention): ~30%
- `memory` (memory_pressure, swap_thrashing): ~20%
- `io` (io_congestion): ~15%
- `load` (load_mismatch): ~10%
- `tcp` (tcp_exhaustion): ~5%
- `scheduler` (thrashing, cpu_starvation): ~10%
- `page_fault` (swap_thrashing): ~10%

---

## Verifying Results

### 1. Check Database Size
```bash
ls -lh data/semantic_stress_test.db
# Should be ~5-20 MB depending on activity
```

### 2. Query Raw Events
```bash
sqlite3 data/semantic_stress_test.db "
SELECT 
    'syscall_events' as table_name, COUNT(*) as count FROM syscall_events
UNION ALL SELECT 'sched_events', COUNT(*) FROM sched_events
UNION ALL SELECT 'memory_metrics', COUNT(*) FROM memory_metrics
UNION ALL SELECT 'signal_metadata', COUNT(*) FROM signal_metadata;
"
```

### 3. Query Semantic Signals
```bash
sqlite3 data/semantic_stress_test.db "
SELECT signal_type, severity, COUNT(*) as count
FROM signal_metadata
GROUP BY signal_type, severity
ORDER BY severity DESC, count DESC;
"
```

### 4. View Critical Observations
```bash
sqlite3 data/semantic_stress_test.db "
.mode column
.headers on
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    signal_type,
    severity,
    summary
FROM signal_metadata
WHERE severity IN ('critical', 'high')
ORDER BY severity DESC, timestamp DESC
LIMIT 10;
"
```

### 5. Sample Natural Language Observations
```bash
sqlite3 data/semantic_stress_test.db "
SELECT summary FROM signal_metadata WHERE severity = 'high' LIMIT 5;
"
```

Expected output like:
```
Memory pressure elevated for 12 minutes - 4.2sigma above normal
I/O bottleneck: stress executing read() blocked for 152.5ms
Swap thrashing: mysql blocked for 85.0ms loading page from disk
Excessive context switching detected for 3 minutes - 15.0sigma above normal
```

---

## Troubleshooting

### Problem: "Permission denied"
**Solution**: Run with `sudo`
```bash
sudo ./scripts/semantic_stress_test.sh
```

### Problem: "scraper_daemon not found"
**Solution**: Build first
```bash
cd build && cmake .. && make -j$(nproc) && cd ..
```

### Problem: No signals created
**Check**:
1. Ingestion daemon logs: `cat logs/semantic_stress_test/semantic_ingestion.log`
2. Look for errors or zero events
3. Verify classifiers loaded: Should see "Semantic ingestion daemon starting..."

### Problem: Very few signals (<10)
**Possible causes**:
- System not under load (stress tool not installed)
- Thresholds too high (normal for idle system)
- Short test duration (use longer test)

### Problem: Test hangs or crashes
**Recovery**:
```bash
# Kill all processes
sudo pkill -f semantic_stress_test
sudo pkill -f stress
sudo pkill -f semantic_ingestion

# Clean up FIFO
sudo rm -f /tmp/kernelsight_semantic

# Check logs
cat logs/semantic_stress_test/*.log
```

---

## Next Steps After Test

### 1. Analyze Signals
```bash
python scripts/analyze_semantic_signals.py data/semantic_stress_test.db
```

### 2. Export for Agent
```bash
# Export observations as JSON for Gemini 3
sqlite3 data/semantic_stress_test.db "
SELECT json_object(
    'summary', summary,
    'severity', severity,
    'patterns', patterns,
    'recommendations', reasoning_hints
) FROM signal_metadata WHERE severity IN ('critical', 'high');
" | jq .
```

### 3. Test Signal Interpreter
```python
from src.pipeline.interpreter import SignalInterpreter
from src.pipeline.features.extractor import FeatureExtractor

# Load features from test
extractor = FeatureExtractor('data/semantic_stress_test.db')
features = extractor.extract_features()

# Interpret as observations
interpreter = SignalInterpreter()
observations = interpreter.interpret(features)

for obs in observations:
    print(f"{obs.severity.value.upper()}: {obs.narrative}")
```

---

## Success Criteria

✅ **Test completes without errors**  
✅ **Raw events: ~20,000-25,000** (all 10 types)  
✅ **Semantic signals: ~100-200** (filtered meaningful observations)  
✅ **Signal distribution: Syscall 30%, Memory 20%, I/O 15%, etc.**  
✅ **Severity: Mix of critical/high/medium/low**  
✅ **Natural language summaries readable by human (and agent)**  
✅ **Database size: 5-20 MB**  
✅ **No Python exceptions in logs**

---

## Alternative: Manual Step-by-Step Test

If automated script fails, run manually:

```bash
# 1. Initialize DB
python3 src/pipeline/semantic_ingestion_daemon.py --init-only --db-path data/test.db

# 2. Start ingestion in background
mkfifo /tmp/test_fifo
python3 src/pipeline/semantic_ingestion_daemon.py --db-path data/test.db < /tmp/test_fifo &

# 3. Start syscall tracer (in WSL)
cd build/src/telemetry
sudo ./syscall_tracer 2>> /tmp/syscall.log | jq -c '{type:"syscall"} + .' >> /tmp/test_fifo &

# 4. Start scraper
sudo ./scraper_daemon --json 2>> /tmp/scraper.log >> /tmp/test_fifo &

# 5. Generate load
stress --cpu 2 --vm 1 --vm-bytes 512M --io 2 --timeout 300s

# 6. Wait and stop
sleep 300
pkill -f stress
pkill -f syscall_tracer
pkill -f scraper_daemon
pkill -f semantic_ingestion

# 7. Check results
sqlite3 data/test.db "SELECT COUNT(*) FROM signal_metadata;"
```

---

## Summary

This test validates the **complete semantic layer pipeline**:
- ✅ Raw telemetry collection (eBPF + scrapers)
- ✅ Semantic classification (4 classifiers, 10 event types)
- ✅ Observation storage (signal_metadata table)
- ✅ Natural language generation
- ✅ Ready for agent consumption

**Goal**: Demonstrate that KernelSight AI transforms raw kernel metrics into agent-readable observations.

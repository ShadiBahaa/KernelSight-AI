# Agent Demo - See Autonomous Decision-Making in Action

## Quick Start

```bash
# Terminal 1: Start the system
sudo python3 run_kernelsight.py

# Terminal 2: Watch agent decisions
python3 monitor_agent.py

# Terminal 3: Watch signals being generated
python3 monitor_signals.py

# Terminal 4: Run the demo workload
sudo bash scripts/agent_demo.sh
```

## What You'll See

The demo runs through **5 phases** to trigger different signal types:

### Phase 1: Memory Pressure (30s)
- **Workload**: Allocates 80% of RAM
- **Signal**: `memory_pressure` (HIGH severity)
- **Agent Should**: 
  - OBSERVE: Detect memory pressure signal
  - EXPLAIN: Flag as abnormal (HIGH severity)
  - SIMULATE: Project OOM risk
  - DECIDE: Choose `clear_page_cache` or `reduce_swappiness`
  - EXECUTE: Run remediation command
  - VERIFY: Check if pressure reduced

### Phase 2: CPU Saturation (30s)
- **Workload**: 8 CPU-intensive processes
- **Signal**: `load_mismatch` (HIGH severity)
- **Agent Should**: 
  - Detect CPU saturation
  - Decide to `lower_process_priority` or `throttle_cpu`
  - Execute action on top CPU consumer

### Phase 3: I/O Congestion (30s)
- **Workload**: Heavy disk I/O
- **Signal**: `io_congestion` (HIGH severity)
- **Agent Should**:
  - Detect I/O queue saturation
  - Decide to `lower_io_priority` or `flush_buffers`
  - Execute I/O throttling

### Phase 4: Network Activity (30s)
- **Workload**: Network stress
- **Signal**: `tcp_exhaustion` or `network_degradation`
- **Agent Should**:
  - Detect TCP or network issues
  - Decide to `increase_tcp_backlog` or `reduce_fin_timeout`
  - Tune network parameters

### Phase 5: Combined Stress (remaining time)
- **Workload**: Multi-dimensional pressure
- **Signals**: Multiple HIGH severity
- **Agent Should**:
  - Prioritize by severity
  - Take multiple remediation actions
  - Verify each one

## Monitoring the Agent

### In monitor_agent.py, you'll see:

```
🟢 Active (updated 2s ago)

📋 RECENT AGENT ACTIVITY
────────────────────────────────────────────────────────────
[Iteration 1] Starting autonomous analysis...
[OBSERVE] Found 3 signals: 2 memory_pressure, 1 load_mismatch
[EXPLAIN] Found 2 abnormal conditions
[SIMULATE] Risk: medium - OOM likely in 30 seconds
[DECIDE] Action: clear_page_cache
[EXECUTE] Running remediation...
[EXECUTE] Command: echo 1 > /proc/sys/vm/drop_caches
[VERIFY] Pressure reduced by 15%
```

### In monitor_signals.py, you'll see:

```
📊 SIGNAL STATISTICS
───────────────────────────────────────────
Total Signals: 145
  memory_pressure: 45 (high: 30, critical: 15)
  load_mismatch: 38 (high: 25, critical: 13)
  io_congestion: 32 (high: 20, critical: 12)
  tcp_exhaustion: 18 (high: 18)
```

## Check Results

After the demo:

```bash
# View agent decisions
tail -100 logs/production/agent.log

# View all signals
sqlite3 data/kernelsight.db "SELECT signal_type, severity, summary FROM signal_metadata ORDER BY timestamp DESC LIMIT 30;"

# View actions taken
grep "EXECUTE" logs/production/agent.log

# View actions resolved
grep "VERIFY.*reduced" logs/production/agent.log
```

## Expected Outcome

You should see the agent:
1. ✅ **Observe** - Detecting HIGH/CRITICAL signals in real-time
2. ✅ **Explain** - Flagging abnormalities based on severity
3. ✅ **Simulate** - Projecting risks (OOM, CPU saturation, etc.)
4. ✅ **Decide** - Choosing appropriate actions from action_schema.py
5. ✅ **Execute** - Running structured remediation commands
6. ✅ **Verify** - Checking if problems were resolved

## Troubleshooting

**If agent isn't taking action:**
- Check severity levels: `sqlite3 data/kernelsight.db "SELECT DISTINCT signal_type, severity FROM signal_metadata;"`
- Signals must be HIGH or CRITICAL to trigger actions
- Lower thresholds in `src/pipeline/signals/system_classifier.py` if needed (TEST thresholds already set very low)

**If no signals generated:**
- Verify system load: `top` (should show stress processes)
- Check ingestion: `grep "events processed" logs/production/ingestion.log`
- Verify scrapers running: `ps aux | grep scraper`

**If agent errors:**
- Check agent log: `tail -f logs/production/agent.log`
- Verify actions available: `python3 -c "from src.agent.action_schema import ActionType; print([a.value for a in ActionType])"`

## Architecture

```
stress_workload → telemetry → signals → agent → actions
     ↓              ↓           ↓        ↓         ↓
  agent_demo.sh  scrapers  classifiers loop   remediation
                 + eBPF                         commands
```

All autonomous! The agent observes, reasons, and acts without human intervention.

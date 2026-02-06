# KernelSight CLI Reference

Professional command-line interface for KernelSight AI system.

## Installation

```bash
# Make executable
chmod +x kernelsight

# Add to PATH (optional)
sudo ln -s $(pwd)/kernelsight /usr/local/bin/kernelsight
```

## Commands

### Query Signals

Query system signals from the database.

```bash
# Query all recent signals
kernelsight query

# Filter by type
kernelsight query --type memory_pressure

# Filter by severity
kernelsight query --severity critical

# Limit results
kernelsight query --limit 10 --lookback 30

# Export as JSON
kernelsight query --type load_mismatch --json
```

**Output (Markdown):**
```markdown
# Signal Query Results

**Summary**
Found 15 signals: 10 memory_pressure, 5 load_mismatch

| Type | Severity | Pressure | Timestamp | Summary |
| --- | --- | --- | --- | --- |
| Memory Pressure | CRITICAL | 0.85 | 16:45:23 | Memory pressure: Only 15.2% available... |
| Load Mismatch | HIGH | 0.62 | 16:45:18 | Load mismatch: 2.5 load on 4 cores... |
```

### Predict Scenarios

Run counterfactual predictions.

```bash
# Predict memory pressure trend
kernelsight predict --signal-type memory_pressure --duration 30

# Predict with custom slope
kernelsight predict --signal-type load_mismatch --duration 60 --slope 0.05

# Export as JSON
kernelsight predict --signal-type io_congestion --json
```

**Output (Markdown):**
```markdown
# Counterfactual Prediction

🔴 **Risk Level**: CRITICAL

## Scenario
If memory_pressure continues at CRITICAL severity, system degradation likely

## Projection
- Current: 0.752
- Projected: 0.934
- Change: +0.182
```

### Agent Operations

Interact with the autonomous agent.

```bash
# Check agent status
kernelsight agent status

# Run agent cycle
kernelsight agent run

# Run with multiple iterations
kernelsight agent run --max-iterations 5

# Export as JSON
kernelsight agent run --json
```

**Output (Markdown):**
```markdown
# Agent Status

🟢 **Status**: ACTIVE

## Recent Activity
- **OBSERVE**: Found 10 signals
- **EXPLAIN**: Found 5 abnormal conditions
- **SIMULATE**: Risk: critical
- **DECIDE**: Action: clear_page_cache
- **EXECUTE**: Success: True
- **VERIFY**: Pressure reduced by 25%
```

## Global Options

| Option | Description |
|--------|-------------|
| `--db PATH` | Database path (default: data/kernelsight.db) |
| `--json` | Output as JSON instead of Markdown |

## Examples

### Demo Workflow

```bash
# 1. Check current state
kernelsight query --severity high

# 2. Predict future issues
kernelsight predict --signal-type memory_pressure --duration 30

# 3. Run agent to fix
kernelsight agent run

# 4. Verify resolution
kernelsight query --type memory_pressure --limit 5
```

### Export for Analysis

```bash
# Export all critical signals as JSON
kernelsight query --severity critical --json > critical_signals.json

# Export prediction
kernelsight predict --signal-type load_mismatch --json > prediction.json

# Export agent results
kernelsight agent run --json > agent_run.json
```

### Integration with Other Tools

```bash
# Pipe to jq for filtering
kernelsight query --json | jq '.signals[] | select(.severity == "critical")'

# Monitor with watch
watch -n 5 'kernelsight query --severity critical --limit 5'

# Alert on anomalies
if kernelsight query --severity critical --json | jq -e '.signal_count > 5' > /dev/null; then
    echo "ALERT: Too many critical signals!"
fi
```

## Use Cases

### For SRE Teams

**Quick Status Check:**
```bash
kernelsight query --severity high
```

**Proactive Monitoring:**
```bash
kernelsight predict --signal-type memory_pressure --duration 60
```

**Manual Intervention:**
```bash
# See what agent would do
kernelsight agent run --max-iterations 1

# Review results
kernelsight query --limit 10
```

### For Demos

**Show Signal Detection:**
```bash
# Clear output
kernelsight query --type memory_pressure
```

**Show Prediction:**
```bash
kernelsight predict --signal-type load_mismatch --duration 30
```

**Show Agent:**
```bash
kernelsight agent run
```

### For Debugging

**Export Everything:**
```bash
# All signals
kernelsight query --limit 1000 --json > all_signals.json

# Predictions
for type in memory_pressure load_mismatch io_congestion; do
    kernelsight predict --signal-type $type --json > predict_$type.json
done

# Agent status
kernelsight agent status --json > agent_status.json
```

## Tips

1. **Use `--json` for scripting** - Easier to parse programmatically
2. **Use Markdown for humans** - Better readability in terminal
3. **Combine with `jq`** - Powerful JSON filtering
4. **Automate with cron** - Schedule periodic checks
5. **Log to files** - Keep history for analysis

## Error Handling

**Database not found:**
```bash
$ kernelsight query
Error: Database not found at data/kernelsight.db
Start the system first: sudo python3 run_kernelsight.py
```

**Agent offline:**
```bash
$ kernelsight agent status
# Agent Status

⚪ **Status**: OFFLINE

Message: Agent not running or no log file found
```

**Invalid parameters:**
```bash
$ kernelsight predict --signal-type invalid_type
Error: No trend data for invalid_type and no custom_slope provided
```

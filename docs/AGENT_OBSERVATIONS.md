# What Gemini 3 Sees: Agent Observation Examples

This document shows **actual observations** that Gemini 3 receives from KernelSight AI's perception layer. These are not metrics—they are semantic signals with natural language narratives.

---

## Observation Format

Each observation contains:
- **Narrative**: Natural language summary
- **Severity**: none, low, medium, high, critical
- **Duration**: How long this has persisted
- **Evidence**: Supporting data
- **Recommendations**: Suggested investigation paths

---

## Example 1: Memory Pressure Crisis

```json
{
  "type": "memory_pressure",
  "severity": "critical",
  "narrative": "Memory availability critically low for 18 minutes (systemic issue) - 5.2sigma above normal",
  "duration_seconds": 1080,
  "first_seen": "2026-01-04T19:21:00Z",
  "last_seen": "2026-01-04T19:39:00Z",
  "evidence": {
    "memory_available_pct": 3.2,
    "baseline_mean": 45.0,
    "zscore": -5.2,
    "swap_used_pct": 78.0,
    "dirty_kb": 1_500_000
  },
  "recommendations": [
    "Critical: System approaching OOM - immediate action required",
    "Identify processes with highest memory usage",
    "Check for memory leaks (steadily increasing RSS)",
    "Correlate with deployment 20 minutes ago"
  ]
}
```

**What the Agent Sees**:
> "The system has been running critically low on memory for 18 minutes. This is a systemic issue, not a transient spike. Memory availability is 5.2 standard deviations below normal. The system is also swapping heavily (78% swap used). This started around the time of a recent deployment."

**Agent Reasoning**:
1. **Pattern Recognition**: Memory pressure + recent deployment = likely leak in new code
2. **Hypothesis**: New deployment introduced memory leak
3. **Tool Call**: `query_process_memory_growth(since=deployment_time)`
4. **Finding**: Process `web-server` RSS grew from 500MB to 6GB linearly
5. **Diagnosis**: Memory leak in web-server process
6. **Action**: Recommend rollback or memory limit enforcement

---

## Example 2: I/O Bottleneck During Backup

```json
{
  "type": "io_bottleneck",
  "severity": "high",
  "narrative": "I/O tail latency spike for 8 minutes - 12.5sigma above baseline",
  "duration_seconds": 480,
  "evidence": {
    "io_read_latency_p99": 450.0,
    "baseline_mean": 15.0,
    "io_queue_depth": 64,
    "max_queue": 128
  },
  "recommendations": [
    "Check disk saturation (queue depth at 50%)",
    "Identify processes with highest I/O rate",
    "Correlate with backup_job scheduled at 19:30"
  ]
}
```

**What the Agent Sees**:
> "I/O operations have severe tail latency (p99 = 450ms vs typical 15ms). The queue is building up. This has persisted for 8 minutes, which is beyond transient variance. The timing correlates with the nightly backup job."

**Agent Reasoning**:
1. **Context**: Backup job started 10 minutes ago
2. **Pattern**: Expected I/O spike during backup, but magnitude unusual
3. **Hypothesis**: Backup + application I/O competing for disk
4. **Tool Call**: `query_syscall_events(syscall=read, sort=latency, limit=20)`
5. **Finding**: Both `backup-agent` and `postgres` doing heavy reads
6. **Diagnosis**: I/O contention between backup and database
7. **Action**: Recommend I/O priority tuning (ionice) for backup, or reschedule

---

## Example 3: Scheduler Thrashing from Fork Bomb

```json
{
  "type": "cpu_contention",
  "severity": "critical",
  "narrative": "Excessive context switching detected for 2 minutes - 45.0sigma above normal",
  "duration_seconds": 120,
  "evidence": {
    "context_switch_rate": 85000,
    "baseline_mean": 2000,
    "process_count": 15234,
    "load_1min": 250.0
  },
  "recommendations": [
    "URGENT: Possible fork bomb or runaway process",
    "Identify processes with highest context switch rates",
    "Check for process explosion (count: 15,234)",
    "Correlate with process creation events"
  ]
}
```

**What the Agent Sees**:
> "Context switch rate spiked to 85,000/sec (45× normal). Process count exploded from ~200 to over 15,000. Load average is 250 on a 4-core system. This is a critical event requiring immediate intervention."

**Agent Reasoning**:
1. **Severity**: Critical alarm — system nearly unresponsive
2. **Pattern**: Fork bomb signature (rapid process creation + thrashing)
3. **Tool Call**: `query_process_tree(sort=child_count)`
4. **Finding**: Process `test-script.sh` has 14,800 children
5. **Diagnosis**: Fork bomb from runaway test script
6. **Action**: Kill process tree immediately, prevent future occurrence

---

## Example 4: Network Degradation (SYN Flood)

```json
{
  "type": "network_degradation",
  "severity": "high",
  "narrative": "Network error rate spiking for 15 minutes (persistent problem) - 8.2sigma above baseline",
  "duration_seconds": 900,
  "evidence": {
    "network_rx_errors": 25000,
    "tcp_syn_recv": 8500,
    "tcp_established": 120,
    "retransmit_rate": 5.2
  },
  "recommendations": [
    "Possible SYN flood attack (8,500 SYN_RECV connections)",
    "Check physical network connectivity",
    "Monitor firewall rules and rate limiting",
    "Correlate with external traffic patterns"
  ]
}
```

**What the Agent Sees**:
> "Network errors are 8× higher than baseline. There are 8,500 connections stuck in SYN_RECV state, which is far higher than the 120 established connections. This has persisted for 15 minutes. Classic SYN flood signature."

**Agent Reasoning**:
1. **Pattern**: SYN_RECV >> ESTABLISHED = likely SYN flood
2. **Impact**: Network degradation, retransmit rate elevated
3. **Tool Call**: `query_tcp_connections(state=SYN_RECV, group_by=remote_ip)`
4. **Finding**: 8,000+ connections from single IP range
5. **Diagnosis**: Distributed SYN flood attack
6. **Action**: Enable SYN cookies, add firewall rules, contact upstream

---

## Example 5: Baseline Learning (Normal Operation)

```json
{
  "type": "baseline",
  "severity": "none",
  "narrative": "System operating normally - all metrics within 1.5sigma of baseline",
  "duration_seconds": 3600,
  "evidence": {
    "memory_available_pct": 48.2,
    "io_latency_p95": 12.0,
    "context_switch_rate": 2100,
    "load_1min": 1.8
  },
  "recommendations": [
    "Use this period for baseline calibration",
    "No action needed"
  ]
}
```

**What the Agent Sees**:
> "All systems nominal. Memory, I/O, CPU, and network metrics are all within expected ranges. This is a good period for refining baseline statistics."

---

## Multi-Signal Correlation Example

Gemini 3 reasons over **multiple observations simultaneously**:

**Scenario**: Deployment → Memory Leak → Swap → I/O Thrashing

```
Observations at T+0 (deployment):
  [INFO] "Deployment event detected"

Observations at T+5min:
  [LOW] "Memory pressure elevated (recent) - 2.1sigma above normal"

Observations at T+10min:
  [MEDIUM] "Memory pressure elevated for 10 minutes - 3.5sigma above normal"
  [LOW] "Page fault rate increasing - 2.0sigma above normal"

Observations at T+15min:
  [HIGH] "System swapping to disk for 5 minutes - 6.0sigma above normal"
  [HIGH] "I/O latency elevated for 5 minutes - 8.5sigma above baseline"
  [MEDIUM] "Memory pressure elevated for 15 minutes (persistent problem)"

Observations at T+18min:
  [CRITICAL] "Memory availability critically low for 18 minutes (systemic issue)"
  [CRITICAL] "Swap thrashing - major page faults spiking"
  [CRITICAL] "I/O bottleneck - p99 latency >500ms"
```

**Agent Correlation Reasoning**:
```
Timeline:
  T+0:  Deployment
  T+5:  Memory starts rising (symptom emerges)
  T+10: Memory pressure persists (not transient)
  T+15: Swap starts, I/O degrades (cascade effect)
  T+18: Critical state (systemic failure)

Pattern: Deployment → Gradual Memory Leak → Swap → I/O Thrashing

Hypothesis: New code leaking memory, causing swap, causing I/O bottleneck

Evidence Chain:
  1. Memory pressure started 5min after deployment ✓
  2. Pressure persisted and worsened (not a spike) ✓
  3. Swap usage followed memory exhaustion ✓
  4. I/O latency spiked when swap started ✓
  5. No other confounding factors (CPU normal, network normal) ✓

Diagnosis: Memory leak in deployed code causing cascading failure

Recommended Action:
  IMMEDIATE: Rollback deployment
  FOLLOW-UP: Identify leaking process, fix code, redeploy with memory limits
```

---

## Agent Perception vs Traditional Monitoring

### Traditional Monitoring Dashboard:
```
memory_available_kb: 2,500,000
memory_total_kb: 32,000,000
swap_used_kb: 15,000,000
io_latency_p99_us: 500,000
context_switch_rate: 85,000
```

**Human interpretation required**: "Is this bad? Let me check baselines... calculate percentages... correlate timing..."

### Agent Perception (What Gemini 3 Sees):
```
[CRITICAL] "Memory availability critically low for 18 minutes (systemic issue) - 5.2sigma above normal"
  → Evidence: 3.2% available (expected 45%)
  → Pattern: Started after deployment
  → Recommendation: Investigate memory leak in recently deployed code

[CRITICAL] "System swapping to disk for 12 minutes - severe performance impact"
  → Evidence: 78% swap used
  → Pattern: Correlates with memory pressure
  → Recommendation: Immediate memory pressure relief needed

[CRITICAL] "I/O tail latency spike for 10 minutes - 12.5sigma above baseline"
  → Evidence: p99 = 500ms (typical 15ms)
  → Pattern: Started when swap began
  → Recommendation: Cascading failure from memory to disk thrashing
```

**Agent interpretation built-in**: "This is a critical memory leak causing swap thrashing. The root cause is the deployment 18 minutes ago. Rollback immediately."

---

## Observation Schema for Gemini 3

Full schema structure:

```typescript
interface AgentObservation {
  // Identity
  type: "memory_pressure" | "io_bottleneck" | "cpu_contention" | 
        "network_degradation" | "anomaly" | "baseline";
  severity: "none" | "low" | "medium" | "high" | "critical";
  
  // Natural Language (PRIMARY INTERFACE)
  narrative: string;  // "Memory pressure elevated for 12 minutes..."
  
  // Temporal Context
  duration_seconds: number;
  first_seen: timestamp;
  last_seen: timestamp;
  persistence_category: "transient" | "short" | "persistent" | "systemic";
  
  // Evidence (for investigation)
  evidence: {
    primary_metric: string;
    current_value: number;
    baseline_mean: number;
    baseline_std: number;
    zscore: number;
    related_metrics: Record<string, number>;
  };
  
  // Actionable Guidance
  recommendations: string[];
  reasoning_hints: string[];
  
  // Correlation
  related_observations: ObservationID[];
  correlated_events: EventID[];
}
```

---

## Key Insights

1. **No Math Required**: Gemini doesn't need to calculate z-scores or interpret percentages
2. **Context Built-In**: Duration, severity, and persistence already determined
3. **Actionable**: Every observation includes investigation hints
4. **Correlatable**: Observations reference each other for multi-signal reasoning
5. **Natural Language**: Reads like a senior SRE explaining the situation

**This is what transforms KernelSight AI from a monitoring tool into an autonomous reasoning agent.**

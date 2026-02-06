# Scheduler Behavioral Patterns for Agent Interpretation

This document describes how different scheduler patterns should be interpreted by Gemini 3 for autonomous system reasoning.

---

## Pattern Categories

### 1. Normal Operation

**Indicators**:
- Context switch rate < 1000/sec
- Involuntary switches < 30%
- Average timeslice 1-10ms
- Balanced CPU utilization

**What It Means**: Healthy scheduler behavior, processes getting fair CPU time

**Agent Response**: No action needed, use as baseline

---

### 2. Busy System

**Indicators**:
- Context switch rate 1000-5000/sec  
- Involuntary switches 30-60%
- Average timeslice 1-10ms
- High but proportional load

**What It Means**: System under load but functioning normally

**Typical Causes**:
- CPU-bound workload (expected)
- Traffic spike or batch job
- Many concurrent tasks

**Agent Reasoning Example**:
```
Observation: nginx switching 3500 times/sec (55% involuntary)
Interpretation: System under load but functioning normally
Evidence: Load average 3.8 on 4-core system (≈1 per core)
Context: Recent traffic spike observed
Hypothesis: Normal response to increased demand
Actions:
  1. Verify load matches expected traffic pattern
  2. Monitor for transition to thrashing
  3. Check runqueue depth stays proportional to core count
```

---

### 3. Scheduling Thrash

**Indicators**:
- Context switch rate > 10,000/sec
- Involuntary switches > 80%
- Average timeslice < 1ms
- Many wakeups with little execution

**What It Means**: CPU cycles wasted on context switching instead of productive work

**Severity Thresholds**:
- **Medium** (10k-20k CS/sec): Noticeable performance impact
- **High** (20k-40k CS/sec): Severe performance degradation
- **Critical** (>40k CS/sec): System nearly unresponsive

**Typical Causes**:
1. **Process explosion** (fork bomb, runaway spawning)
2. **Lock contention cascade** (thundering herd on futex)
3. **Too many short-lived tasks** (inefficient task spawning)
4. **Scheduler bug or misconfiguration**

**Agent Reasoning Example**:
```
Observation: stress switching 15000 times/sec (87% involuntary), avg timeslice 0.001ms
Interpretation: Scheduling thrash - CPU wasted on context switches
Evidence: Extremely short timeslices indicate rapid preemption
Context: Involuntary rate critical (87%)
Hypothesis: Process explosion or lock contention
Actions:
  1. Identify top context switchers (likely culprits)
  2. Check process count for explosion
  3. Correlate with futex syscall latency
  4. Look for thundering herd pattern (many threads same PID)
```

**Specific Pattern: Thundering Herd**:
```
Observation: High wakeup-to-context-switch ratio (>5.0)
Interpretation: Many threads waking but not executing
Evidence: Wakeups >> context switches
Pattern: Broadcast wakeup on lock/condition variable
Impact: CPU wasted on wakeups, only one thread proceeds
Remediation: Use targeted wakeups (FUTEX_WAKE_OP), redesign locking
```

---

### 4. CPU Starvation

**Indicators**:
- Runqueue depth >> core count (>3× cores)
- High voluntary switches (processes yielding)
- Long wait times for CPU
- Load average >> core count

**What It Means**: Processes can't get CPU time despite being runnable

**Severity Thresholds**:
- **Medium**: Runqueue >3× cores
- **High**: Runqueue >5× cores  
- **Critical**: Runqueue >10× cores

**Typical Causes**:
1. **Too many runnable processes** (demand exceeds capacity)
2. **High-priority monopoly** (real-time tasks starving others)
3. **CPU affinity pinning** (many tasks pinned to few cores)
4. **Scheduler imbalance** (uneven load across CPUs)

**Agent Reasoning Example**:
```
Observation: postgres waiting for CPU, runqueue depth 45 on 4-core system
Interpretation: CPU starvation - >10× more demand than capacity
Evidence: Runqueue depth 11.25× core count
Context: Load average 18.5 (>>4 cores)
Hypothesis: Too many concurrent processes or priority inversion
Actions:
  1. Identify which processes are runnable but not running
  2. Check for CPU affinity constraints
  3. Look for real-time priority tasks monopolizing CPU
  4. Consider process count reduction or scaling horizontally
```

---

### 5. Lock Contention Induced Churn

**Indicators**:
- High wakeup-to-CS ratio (>2.0)
- Low involuntary switch percentage (<30%)
- Many wakeups with few context switches
- Correlates with high futex latency

**What It Means**: Threads rapidly waking to acquire locks but immediately blocking

**Typical Causes**:
- **Lock holder slow** (holding lock while doing I/O)
- **Thundering herd** (broadcast wakeup, only one succeeds)
- **Hot lock** (many threads contending for same lock)
- **Priority inversion** (low-priority thread holding lock)

**Agent Reasoning Example**:
```
Observation: nginx worker waking 5× more than switching (low involuntary rate)
Interpretation: Lock contention cascade - waking to acquire locks, then blocking
Evidence: Wakeup/CS ratio = 5.2, involuntary = 25%
Context: Correlates with futex() latency spike to 75ms
Hypothesis: Multiple workers blocking on shared resource lock
Actions:
  1. Correlate with futex syscall events (confirm lock contention)
  2. Identify lock owner if possible
  3. Check if lock held during I/O (inefficient)
  4. Review application locking strategy
```

---

### 6. Scheduler Imbalance

**Indicators**:
- Uneven runqueue depths across CPUs
- Some CPUs heavily loaded, others idle
- CPU affinity constraints present
- NUMA effects

**What It Means**: Load not evenly distributed across available CPUs

**Typical Causes**:
1. **CPU affinity pinning** (manual taskset or cgroup constraints)
2. **NUMA topology** (memory locality keeping tasks on certain CPUs)
3. **Scheduler migration hesitancy** (avoiding cache thrashing)
4. **Asymmetric workload** (inherently unbalanced)

**Agent Reasoning Example**:
```
Observation: CPUs 0-1 runqueue depth 15, CPUs 2-3 runqueue depth 2
Interpretation: Scheduler imbalance - uneven load across CPUs
Evidence: 7.5× difference in runqueue depth
Context: Application uses CPU affinity masks
Hypothesis: Tasks pinned to specific CPUs, preventing migration
Actions:
  1. Check CPU affinity settings (taskset, cgroup cpu.affinity)
  2. Verify NUMA node placement
  3. Consider removing affinity constraints if not intentional
  4. Evaluate load balancer tuning parameters
```

---

## Cross-Pattern Correlations

Gemini 3 should look for combinations:

### Correlation 1: Thrashing + Lock Contention
```
IF scheduling_thrash TRUE
   AND futex_syscall_latency HIGH
   AND wakeup_cs_ratio > 2.0
THEN "Lock contention causing scheduling cascade"
     "Multiple threads competing for locks"
     " Solution: Fix lock contention, not scheduler"
```

### Correlation 2: CPU Starvation + I/O Wait
```
IF cpu_starvation TRUE
   AND load_average HIGH
   AND io_latency LOW
THEN "CPU-bound starvation (not I/O)"
     "Too many compute tasks"
     "Solution: Reduce parallelism or add CPU cores"
```

### Correlation 3: Imbalance + Memory Pressure
```
IF scheduler_imbalance TRUE
   AND memory_pressure_per_numa_node VARIES
THEN "NUMA-induced imbalance"
     "Tasks staying near memory"
     "Solution: Consider NUMA-aware memory allocation"
```

---

## Metrics Dictionary

| Metric | Meaning | Good | Concerning | Critical |
|--------|---------|------|------------|----------|
| **Context Switches/sec** | Rate of task switches | <1000 | 5000-10000 | >20000 |
| **Involuntary %** | Forced preemptions | <30% | 60-80% | >80% |
| **Avg Timeslice (ms)** | Time before preemption | 1-10ms | 0.1-1ms | <0.1ms |
| **Wakeup/CS Ratio** | Wakeups per switch | 0.5-1.5 | 2.0-5.0 | >5.0 |
| **Runqueue Depth** | Tasks waiting for CPU | <cores | 3-5× cores | >10× cores |

---

## Temporal Analysis

**Transient** (<10 seconds):
- GC pause, transient spike
- Log but don't alert

**Short-lived** (10-60 seconds):
- Monitor for recurrence
- May be temporary workload

**Persistent** (1-15 minutes):
- Investigate actively
- Clear performance issue

**Systemic** (>15 minutes):
- Urgent attention
- System degradation ongoing

---

## Integration with Other Signals

### With Syscall Signals:
- Thrashing + High futex latency → Lock contention
- CPU starvation + High I/O latency → I/O blocking tasks

### With Memory Signals:
- Thrashing + Page faults → Memory thrashing (swap)
- Imbalance + NUMA pressure → Memory locality issues

### With Load Signals:
- CPU starvation + Load >> cores → Oversubscription
- Normal scheduler + High load → Expected busy state

---

## Usage Example

```python
from src.pipeline.signals import SchedulerSemanticClassifier

classifier = SchedulerSemanticClassifier(num_cpus=4)

# Raw event from scheduler tracer
event = {
    'time_bucket': 12345,
    'pid': 1234,
    'comm': 'stress',
    'context_switches': 15000,
    'voluntary_switches': 2000,
    'involuntary_switches': 13000,
    'wakeups': 8000,
    'cpu_time_ns': 500_000_000,
    'total_timeslice_ns': 15_000_000,
    'timeslice_count': 15000
}

# Transform to observation
obs = classifier.create_observation(event)

print(obs.summary)
# "Scheduling thrash detected: stress switching 15000 times/sec (87% involuntary)"

print(obs.state)
# SchedulerState.THRASHING

print(obs.severity)
# SeverityLevel.HIGH

for pattern in obs.patterns:
    print(f"  - {pattern}")
# - Very short timeslices (0.00ms) - rapid preemption
# - 87% involuntary switches - processes forced off CPU
# - Excessive context switching (15000/sec)
```

---

## Future Enhancements

**Gaps Still To Address**:
1. ✅ Semantic labels (DONE with 6 states)
2. ❌ **Runqueue depth tracking** - Needs BPF tracer addition
3. ❌ **Per-CPU analysis** - Needs BPF per-CPU runqueue tracking

**Recommended BPF Additions**:
```c
// Add to sched_tracer.bpf.c
struct runqueue_stats {
    __u32 cpu;
    __u32 nr_running;  // Tasks in runqueue
    __u64 timestamp;
};

// Track per-CPU runqueue depth
SEC("tp/sched/sched_switch")
int track_runqueue_depth(ctx) {
    __u32 cpu = bpf_get_smp_processor_id();
    // Get nr_running from task_struct or rq
    // Emit runqueue depth per CPU
}
```

This would enable full per-CPU imbalance detection for Gemini 3.

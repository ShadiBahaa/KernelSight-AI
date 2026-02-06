# Semantic Layer Architecture Explained

## What is the Semantic Layer?

The semantic layer is **NOT per log file** and **NOT per database table**. 

It's a **signal processing layer** that sits **between raw telemetry and the agent**, transforming raw numbers into meaningful observations.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAW TELEMETRY SOURCES                        │
├─────────────────────────────────────────────────────────────────┤
│  eBPF Tracers          │  Scrapers (/proc, /sys)                │
│  - syscall_tracer      │  - /proc/meminfo (memory)              │
│  - sched_tracer        │  - /proc/loadavg (load)                │
│  - io_tracer           │  - /sys/block/*/stat (I/O)             │
│  - pagefault_tracer    │  - /proc/net/dev (network)             │
│                        │  - /proc/net/tcp (TCP)                 │
└────────────┬───────────┴────────────────────────────────────────┘
             │
             │ Raw Events (JSON)
             │ Example: {"timestamp": 12345, "latency_ns": 152500000, ...}
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    SEMANTIC LAYER (NEW!)                        │
├─────────────────────────────────────────────────────────────────┤
│  3 Semantic Classifiers:                                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐          │
│  │ SyscallSemanticClassifier                        │          │
│  │ Input:  syscall events from syscall_tracer       │          │
│  │ Output: Behavioral observations                  │          │
│  │   - Category: blocking_io, lock_contention, etc  │          │
│  │   - Severity: low/medium/high/critical           │          │
│  │   - Summary: "I/O bottleneck: postgres blocked"  │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐          │
│  │ SchedulerSemanticClassifier                      │          │
│  │ Input:  sched events from sched_tracer           │          │
│  │ Output: Scheduler state observations             │          │
│  │   - State: thrashing, cpu_starvation, normal     │          │
│  │   - Summary: "Scheduling thrash: 15k CS/sec"     │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐          │
│  │ SystemMetricsClassifier                          │          │
│  │ Input:  memory, load, I/O, network, TCP metrics  │          │
│  │ Output: Pressure observations                    │          │
│  │   - Type: memory_pressure, io_congestion, etc    │          │
│  │   - Summary: "Memory pressure: Only 5% avail"    │          │
│  └──────────────────────────────────────────────────┘          │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Semantic Observations (Structured)
             │ Example: {type: "io_bottleneck", severity: "high", 
             │          summary: "I/O latency elevated...", ...}
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE STORAGE                             │
├─────────────────────────────────────────────────────────────────┤
│  Raw Tables (10)         │  Semantic Table (1)                  │
│  - syscall_events        │  - signal_metadata                   │
│  - sched_events          │    └─ All semantic observations      │
│  - memory_metrics        │       from all classifiers           │
│  - load_metrics          │                                      │
│  - io_latency_stats      │                                      │
│  - block_stats           │                                      │
│  - network_stats         │                                      │
│  - tcp_stats             │                                      │
│  - page_fault_events     │                                      │
│  - tcp_retransmit_stats  │                                      │
└─────────────────────────┴──────────────────────────────────────┘
```

---

## Key Points

### 1. **Per EVENT TYPE, Not Per Log**

The semantic layer processes **event types**, not log files:

| Event Type | Classifier Used | Applied? |
|------------|----------------|----------|
| **Syscall events** | SyscallSemanticClassifier | ✅ Yes |
| **Scheduler events** | SchedulerSemanticClassifier | ✅ Yes |
| **Memory metrics** | SystemMetricsClassifier | ✅ Yes |
| **Load metrics** | SystemMetricsClassifier | ✅ Yes |
| **I/O stats** | SystemMetricsClassifier | ✅ Yes |
| **Network stats** | SystemMetricsClassifier | ✅ Yes |
| **TCP stats** | SystemMetricsClassifier | ✅ Yes |
| **Block stats** | SystemMetricsClassifier | ⚠️ Partial* |
| **Page faults** | (Future classifier) | ❌ Not yet |
| **TCP retransmit** | SystemMetricsClassifier | ✅ Yes |

*Block stats could be added to SystemMetricsClassifier if needed

### 2. **NOT Every Event Becomes a Signal**

**Important**: The semantic layer is **selective**:

```python
# Example: Syscalls
Raw events: 10,000 syscalls captured
↓
Classifier filters: Only high-latency (>10ms)
↓
Semantic signals: ~200 observations (2%)
```

**Why?** Only **meaningful deviations** become observations:
- ✅ `latency = 152ms` → Signal: "I/O bottleneck detected"
- ❌ `latency = 2ms` → No signal (normal)

### 3. **One Unified Signal Table**

All semantic observations go into **ONE table**: `signal_metadata`

```sql
-- signal_metadata contains observations from ALL classifiers:
SELECT signal_type, COUNT(*) FROM signal_metadata GROUP BY signal_type;

syscall     | 45   -- from SyscallSemanticClassifier
scheduler   | 12   -- from SchedulerSemanticClassifier  
memory      | 8    -- from SystemMetricsClassifier
io          | 15   -- from SystemMetricsClassifier
tcp         | 3    -- from SystemMetricsClassifier
```

---

## Data Flow Example

Let's trace **one syscall** through the layers:

### Step 1: Raw eBPF Event
```json
{
  "type": "syscall",
  "timestamp": 1704470400000000000,
  "pid": 1234,
  "comm": "postgres",
  "syscall_name": "read",
  "latency_ns": 152500000,
  "ret_value": 4096
}
```

### Step 2: Stored in Raw Table
```sql
INSERT INTO syscall_events 
  (timestamp, pid, comm, syscall_name, latency_ns, ret_value)
VALUES (1704470400000000000, 1234, 'postgres', 'read', 152500000, 4096);
-- Row ID: 42
```

### Step 3: Processed by Semantic Classifier
```python
classifier = SyscallSemanticClassifier()
obs = classifier.create_observation(event)

# obs.category = BLOCKING_IO
# obs.severity = HIGH
# obs.summary = "I/O bottleneck: postgres executing read() blocked for 152.5ms"
# obs.patterns = ["Slow read operation (disk seek or cache miss)"]
```

### Step 4: Stored in Semantic Table
```sql
INSERT INTO signal_metadata
  (timestamp, signal_type, semantic_label, severity, summary, 
   source_table, source_id, entity_type, entity_id, entity_name)
VALUES 
  (1704470400000000000, 'syscall', 'blocking_io', 'high',
   'I/O bottleneck: postgres executing read() blocked for 152.5ms',
   'syscall_events', 42, 'process', '1234', 'postgres');
```

### Result

**Two records created**:
1. **Raw**: `syscall_events` table (row 42) - preserves exact data
2. **Semantic**: `signal_metadata` table - agent-facing observation

---

## Coverage Summary

### ✅ Fully Implemented (Days 2-6)

| Layer | Input | Output | Count |
|-------|-------|--------|-------|
| **Syscall Semantic** | syscall_events | Behavioral categories (10 types) | ~50-100 signals/hour |
| **Scheduler Semantic** | sched_events | CPU states (6 types) | ~10-20 signals/hour |
| **System Semantic** | memory/load/io/net/tcp | Pressure indicators (6 types) | ~20-40 signals/hour |

### ❌ Not Yet Implemented

| Layer | Reason |
|-------|--------|
| **Page Fault Semantic** | Needs dedicated classifier (could use memory pressure) |
| **Block Device Semantic** | Could extend SystemMetricsClassifier |

---

## Why This Design?

### 1. **Separation of Concerns**
- **Raw tables**: Forensic analysis, historical data, compliance
- **Signal table**: Agent reasoning, real-time decisions

### 2. **Efficiency**
- Don't create signals for every event (100k+ events/hour)
- Only meaningful deviations (~100-200 signals/hour)

### 3. **Flexibility**
- Can query raw data when needed
- Can add/change classifiers without touching raw storage
- Can reprocess historical raw data with new classifiers

### 4. **Agent-Friendly**
- Gemini 3 queries `signal_metadata` only
- Gets natural language summaries, not numbers
- No math or interpretation needed

---

## Quick Lookup Table

**"Where does X get processed?"**

| Data Source | Raw Table | Classifier | Signal Type |
|-------------|-----------|------------|-------------|
| syscall_tracer | syscall_events | SyscallSemanticClassifier | `syscall` |
| sched_tracer | sched_events | SchedulerSemanticClassifier | `scheduler` |
| /proc/meminfo | memory_metrics | SystemMetricsClassifier | `memory` |
| /proc/loadavg | load_metrics | SystemMetricsClassifier | `load` |
| /sys/block/*/stat | block_stats | SystemMetricsClassifier | `io` |
| /proc/net/dev | network_stats | SystemMetricsClassifier | `network` |
| /proc/net/tcp | tcp_stats | SystemMetricsClassifier | `tcp` |
| io_tracer | io_latency_stats | SystemMetricsClassifier | `io` |
| pagefault_tracer | page_fault_events | (None yet) | - |

---

## Summary

**The semantic layer is**:
- ✅ **Per event type** (syscalls, scheduler, memory, etc.)
- ✅ **Selective** (only meaningful observations)
- ✅ **Applied to most types** (7 out of 10)
- ✅ **Stored in one unified table** (`signal_metadata`)

**The semantic layer is NOT**:
- ❌ Per log file
- ❌ Per database table
- ❌ Applied to every single event
- ❌ A replacement for raw data

**Result**: Raw data preserved for forensics, semantic observations created for agent reasoning.

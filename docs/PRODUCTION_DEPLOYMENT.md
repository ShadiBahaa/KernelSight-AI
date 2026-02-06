# KernelSight AI - Production Deployment

This guide explains how to run the complete KernelSight AI system in production mode.

## Overview

The production system consists of **8 integrated components** that run continuously:

```
┌────────────────────────────────────────────────────────────────────┐
│                      KernelSight AI System                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│   │  Syscall    │ │ Scheduler   │ │ Page Fault  │ │ I/O Latency │  │
│   │  Tracer     │ │ Tracer      │ │ Tracer      │ │ Tracer      │  │
│   │  (eBPF)     │ │ (eBPF)      │ │ (eBPF)      │ │ (eBPF)      │  │
│   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘  │
│          │               │               │               │         │
│          │    ┌──────────────────┐       │               │         │
│          │    │ Scraper Daemon   │       │               │         │
│          │    │ (System Metrics) │       │               │         │
│          │    └────────┬─────────┘       │               │         │
│          │             │                 │               │         │
│          └─────────────┴─────────────────┴───────────────┘         │
│                                │                                   │
│                                │ JSON Events                       │
│                                ▼                                   │
│                    ┌───────────────────────┐                       │
│                    │  Semantic Ingestion   │                       │
│                    │  Daemon               │ ──► SQLite Database   │
│                    └───────────┬───────────┘    (signal_metadata)  │
│                                │                                   │
│                                │ Semantic Signals                  │
│                                ▼                                   │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │                                                         │    │
│     │  ┌───────────────────┐     ┌───────────────────┐        │    │
│     │  │ Autonomous Agent  │     │ Interactive Agent │        │    │
│     │  │ (Background loop) │     │ (Chat interface)  │        │    │
│     │  │ Gemini 3 Flash    │     │ Gemini 3 Flash    │        │    │
│     │  │ ──► Auto Actions  │     │ ──► Human Queries │        │    │
│     │  └───────────────────┘     └───────────────────┘        │    │
│     │                                                         │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

Ensure you have built the project:

```bash
cd /path/to/KernelSight\ AI
mkdir -p build && cd build
cmake .. -DBUILD_EBPF=ON
make -j$(nproc)
```

### 2. Run the System

```bash
# Run with default settings (auto-creates venv, installs deps, prompts for API key)
./start_kernelsight.sh

# Run without autonomous agent
./start_kernelsight.sh --no-agent

# Change agent check interval (default: 60s)
./start_kernelsight.sh --agent-interval 30
```

### 3. Monitor the System

The system will create logs in `logs/production/`:

```bash
# View all logs in real-time
tail -f logs/production/*.log

# View agent decisions
tail -f logs/production/agent.log

# View ingestion statistics
tail -f logs/production/ingestion.log

# Query semantic signals from database
sqlite3 data/kernelsight.db "SELECT signal_type, severity, summary FROM signal_metadata ORDER BY timestamp DESC LIMIT 10;"
```

## System Components

### 1. **eBPF Tracers** (Real-time Kernel Monitoring)

| Tracer | What it monitors | Output frequency |
|--------|-----------------|------------------|
| `syscall_tracer` | High-latency system calls (>10ms) | Per-event |
| `sched_tracer` | Context switches, CPU time | Per-event |
| `page_fault_tracer` | Memory page faults (major/minor) | Per-event |
| `io_latency_tracer` | Block I/O operations with latency percentiles | Every 5s |

All eBPF tracers output **JSON events** to stdout.

### 2. **Scraper Daemon** (System-wide Metrics)

Collects metrics from `/proc` and `/sys`:
- **Memory**: Available, buffers, cached, swap
- **Load**: Load average, CPU count
- **Block devices**: Read/write operations, bytes, latency
- **Network interfaces**: RX/TX packets, bytes, errors
- **TCP statistics**: Connections, retransmits

Outputs **JSON metrics** every 5 seconds.

### 3. **Semantic Ingestion Daemon** (Event Processing)

Receives JSON events from all tracers/scrapers and:
- Stores raw data in database tables (`syscall_events`, `memory_metrics`, etc.)
- **Classifies events** using semantic classifiers:
  - `SyscallSemanticClassifier`: Identifies slow I/O, blocking calls
  - `SchedulerSemanticClassifier`: Detects CPU saturation, runaway processes
  - `PageFaultSemanticClassifier`: Identifies memory pressure, thrashing
  - `SystemMetricsClassifier`: Detects OOM risk, I/O congestion, network degradation
- Stores **semantic signals** in `signal_metadata` table with:
  - Signal type (e.g., `memory_pressure`, `io_congestion`)
  - Severity (`low`, `medium`, `high`, `critical`)
  - Natural language summary
  - Pressure score (0.0 - 1.0)

### 4. **Autonomous Agent** (AI-Powered Remediation)

Runs a continuous loop every N seconds (default: 60s):

#### Agent Cycle (6 Phases):

1. **OBSERVE**: Query recent semantic signals from database
2. **EXPLAIN**: Analyze what's abnormal and why
3. **SIMULATE**: Project future states using trend analysis
4. **DECIDE**: Choose remediation action using Gemini 3 (or rule-based fallback)
5. **EXECUTE**: Run action via structured command framework
6. **VERIFY**: Check if problem was resolved

#### Example Agent Actions:

| Problem | Action Taken |
|---------|-------------|
| OOM risk detected | Lower priority of memory-hungry process |
| CPU saturation | Throttle CPU-intensive process |
| I/O congestion | Reduce I/O priority of heavy processes |
| Swap thrashing | Adjust vm.swappiness kernel parameter |

All actions are **audited** with justification, expected effect, and confidence score.

## Configuration

### Database Schema

The system uses SQLite with these key tables:

- **Raw data tables**: `syscall_events`, `sched_events`, `page_fault_events`, `memory_metrics`, `load_metrics`, `io_latency_stats`, `block_stats`, `network_interface_stats`, `tcp_stats`
- **Semantic signals**: `signal_metadata` (the "agent's memory")
- **Baselines**: `baseline_snapshots` (for anomaly detection)

### Agent Configuration

Pass command-line arguments to `start_kernelsight.sh`:

```bash
# Agent check interval (seconds)
./start_kernelsight.sh --agent-interval 30

# Disable agent
./start_kernelsight.sh --no-agent
```

## Operational Modes

### Mode 1: Full Autonomous Operation (Default)

All components run together. Agent monitors and takes actions automatically.

```bash
./start_kernelsight.sh
```

### Mode 2: Data Collection Only

Collect and classify data, but no autonomous actions.

```bash
./start_kernelsight.sh --no-agent
```

### Mode 3: Custom Agent Interval

Run agent more/less frequently:

```bash
# High-frequency monitoring (every 30s)
./start_kernelsight.sh --agent-interval 30

# Low-frequency monitoring (every 5 minutes)
./start_kernelsight.sh --agent-interval 300
```


**Recommendation**: Run only eBPF tracers as root, use `setcap` if possible.

## Troubleshooting

### Issue: eBPF tracers fail to start

```bash
# Check BTF support
ls -la /sys/kernel/btf/vmlinux

# Check kernel version
uname -r

# Re-generate vmlinux.h
cd build && cmake .. && make
```

### Issue: No signals in database

```bash
# Check if ingestion daemon is processing events
tail -f logs/production/ingestion.log

# Check if tracers are producing output
tail -f logs/production/syscall.log

# Verify database tables exist
sqlite3 data/kernelsight.db ".tables"
```

### Issue: Agent not taking actions

```bash
# Check agent logs
tail -f logs/production/agent.log

# Verify signals exist
sqlite3 data/kernelsight.db "SELECT * FROM signal_metadata LIMIT 10;"

# Check if Gemini API key is set (optional)
echo $GEMINI_API_KEY
```

## Stopping the System

Close all terminal windows.

## Next Steps

Once the system is running:

1. **Generate workload** to create signals:
   ```bash
   # CPU stress
   stress-ng --cpu 4 --timeout 60s
   
   # Memory stress
   stress-ng --vm 2 --vm-bytes 1G --timeout 60s
   
   # I/O stress
   dd if=/dev/zero of=/tmp/test bs=1M count=1000
   ```

2. **Monitor agent behavior** and see how the autonmous loop terminal detects and resolves the problem. You can also chat with the interactive agent to get more info about your system health.

## Architecture Highlights

### Why This Design?

1. **Real-time**: eBPF tracers capture kernel events with <1ms latency
2. **Semantic**: Raw events → meaningful signals (e.g., "OOM risk" not just "low memory")
3. **Autonomous**: Agent makes decisions based on signal patterns, trends, and simulations
4. **Auditable**: Every action logged with justification and confidence

### Data Flow

```
Kernel Events → eBPF Tracers → JSON Stream → 
Semantic Ingestion → signal_metadata table →
Agent OBSERVE → EXPLAIN → SIMULATE → DECIDE → EXECUTE
```

### Process Model (GUI Terminal Windows)

Each component runs in its own **gnome-terminal window**:

- **Syscall Tracer** - eBPF tracer for high-latency system calls
- **Scheduler Tracer** - eBPF tracer for context switches
- **Page Fault Tracer** - eBPF tracer for memory page faults
- **I/O Latency Tracer** - eBPF tracer for block I/O latency
- **Scraper Daemon** - System metrics from /proc and /sys
- **Ingestion Daemon** - Receives JSON, stores to database
- **Autonomous Agent** - Periodic monitoring and remediation
- **Interactive Agent** - Chat interface for human queries

Components communicate via **stdout → stdin pipes** and **SQLite database**.

---

**Questions?** Check the docs or examine the code:
- `start_kernelsight.sh`: Main launcher script
- `src/pipeline/semantic_ingestion_daemon.py`: Event processing
- `src/agent/autonomous_loop.py`: Agent decision cycle
- `src/agent/agent_tools.py`: Tool implementations

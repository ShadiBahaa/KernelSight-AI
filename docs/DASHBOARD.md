# Real-Time Dashboard Guide

## Quick Start

```bash
# Install Rich library
pip install rich

# Run the dashboard
python3 dashboard.py
```

## Features

### 📊 Live Signal Detection
- Real-time signal counts by type
- Severity indicators (🟢 Normal, 🟠 High, 🔴 Critical)
- Auto-updating every 0.5 seconds

### 🚨 Anomaly Alerts
- Last 5 critical/high severity events
- Timestamps and summaries
- Color-coded by severity

### 🤖 Agent Status
- Current phase visualization (OBSERVE → EXPLAIN → SIMULATE → DECIDE → EXECUTE → VERIFY)
- Live activity log
- Active/Idle status indicator

### 📈 Statistics
- Total signal count
- Anomaly count
- Database connection status

## Layout

```
┌─────────────────────────────────────────────────────────┐
│         ⚡ KernelSight AI - Autonomous SRE Agent        │
├────────────────────────┬────────────────────────────────┤
│  📊 Signal Detection   │  🤖 Agent Status               │
│  - memory_pressure     │  [1] OBSERVE → [2] EXPLAIN →   │
│  - load_mismatch       │  [3] SIMULATE → [4] DECIDE →   │
│  - io_congestion       │  [5] EXECUTE → [6] VERIFY      │
├────────────────────────┼────────────────────────────────┤
│  🚨 Recent Anomalies   │  📈 Statistics                 │
│  22:45:12 CRITICAL     │  Total Signals: 1,245          │
│  22:44:58 HIGH         │  Anomalies: 15                 │
├────────────────────────┴────────────────────────────────┤
│  ℹ️  Help: q=Quit • p=Pause • r=Reset • 1-6=Jump       │
└─────────────────────────────────────────────────────────┘
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit dashboard |
| `p` | Pause/Resume updates |
| `r` | Reset statistics |
| `1-6` | Jump to specific agent phase |

## Color Coding

- 🔴 **Red**: Critical severity (immediate action required)
- 🟠 **Orange**: High severity (monitoring closely)
- 🟢 **Green**: Normal/healthy status
- 🔵 **Blue**: Information
- 🟡 **Yellow**: Warnings

## Demo Usage

For hackathon demos, run three terminals:

**Terminal 1: System**
```bash
sudo python3 run_kernelsight.py
```

**Terminal 2: Dashboard** (THIS IS YOUR MAIN DISPLAY!)
```bash
python3 dashboard.py
```

**Terminal 3: Stress Test**
```bash
sudo bash scripts/agent_demo.sh
```

The dashboard will show:
1. ✅ Signals appearing in real-time
2. ✅ Anomalies highlighted in red/orange
3. ✅ Agent working through phases
4. ✅ Actions being executed
5. ✅ Results being verified

## Why This Matters for Hackathon

**Before this dashboard:**
- Had to tail multiple log files
- No visual overview
- Hard to see autonomous behavior

**With this dashboard:**
- ✨ **Instant visual impact** when judges see it
- ✨ **Clear autonomous workflow** (phases light up)
- ✨ **Real-time anomaly detection** (red alerts)
- ✨ **Professional presentation quality**

The dashboard makes your technical depth **visible and impressive**! 🎯

## Troubleshooting

**Dashboard won't start:**
```bash
# Install Rich
pip install rich

# Check database exists
ls -la data/kernelsight.db
```

**No data showing:**
- Make sure `run_kernelsight.py` is running
- Wait 30 seconds for signals to appear
- Run stress test to generate activity

**Slow updates:**
- Normal - updates every 0.5s
- Database queries are intentionally throttled for performance

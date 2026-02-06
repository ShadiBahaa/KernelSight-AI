# KernelSight AI

**Autonomous SRE Agent powered by eBPF + Gemini AI**

> Real-time kernel telemetry, predictive analytics, and autonomous remediation - all in one system.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Linux Kernel 5.15+](https://img.shields.io/badge/kernel-5.15+-green.svg)](https://www.kernel.org/)

## ✨ Features

### 📊 **Real-Time Monitoring**
- **eBPF-based collection**: Syscalls, scheduler events, I/O latency, page faults
- **System metrics scraping**: Memory, CPU, network, disk statistics
- **Anomaly highlighting**: Automatic detection of critical issues

### 🤖 **Autonomous Agent**
- **6-Phase Decision Cycle**: OBSERVE → EXPLAIN → SIMULATE → DECIDE → EXECUTE → VERIFY
- **Gemini-powered reasoning**: Understands system state, not just pattern matching
- **Autonomous remediation**: Safely executes fixes (page cache clearing, process priority, etc.)
- **Dynamic confidence scoring**: Risk-aware action selection
- **Human-in-the-loop**: Requires approval before executing any commands (You can disable this feature!)

### � **Interactive Agent**
- **Natural language interface**: Ask questions about system health in plain English
- **Tool-augmented reasoning**: Accesses real-time signals, baselines, and command execution
- **Context-aware responses**: Maintains conversation history for follow-up questions
- **Human-in-the-loop**: Requires approval before executing any commands (You can disable this feature!)

### 🧪 **Production Ready**
- **10+ automated tests**: Unit, integration, and chaos tests
- **Comprehensive logging**: Structured logs with rotation
- **Auto-setup**: Virtual environment and dependency management

## 🚀 Quick Start

### Prerequisites

- **Linux** (Ubuntu 22.04+ recommended) or WSL2
- **Kernel 5.15+** with BTF support
- **Python 3.9+**
- **CMake 3.16+** and build tools

### Installation

```bash
# Clone the repository
git clone https://github.com/ShadiBahaa/KernelSight-AI
cd KernelSight-AI

# Build eBPF tracers
mkdir -p build && cd build
cmake ..
make -j$(nproc)
cd ..

# Run the system (auto-creates venv, installs deps, prompts for API key)
./start_kernelsight.sh
```

### Run Options

```bash
# Opens each component in a separate terminal window
./start_kernelsight.sh

# Without autonomous agent (data collection only)
./start_kernelsight.sh --no-agent

# Custom agent interval (default: 60s)
./start_kernelsight.sh --agent-interval 30
```

**What runs:**
- eBPF tracers (syscall, scheduler, page_fault, io_latency)
- System metrics scraper
- Semantic ingestion daemon (raw events → semantic signals)
- Autonomous agent (monitors signals → takes actions)
- Interactive agent (chat with the system)

Monitor the system:
```bash
# View all logs
tail -f logs/production/*.log

# Query semantic signals
sqlite3 data/kernelsight.db "SELECT * FROM signal_metadata ORDER BY timestamp DESC LIMIT 10;"
```

See **[Production Deployment Guide](docs/PRODUCTION_DEPLOYMENT.md)** for complete details.

### Manual Component Testing

```bash
# Initialize database only
python src/pipeline/semantic_ingestion_daemon.py --init-only --db-path test.db

# Test individual components
./build/src/telemetry/scraper_daemon | python src/pipeline/semantic_ingestion_daemon.py

# Query collected data
python src/pipeline/query_utils.py --demo
```

## 🧪 Testing

### Quick Pipeline Test (Linux)
```bash
# Automated test with real collectors (30 seconds)
chmod +x scripts/quick_pipeline_test.sh
./scripts/quick_pipeline_test.sh
```

### Full End-to-End Test (Linux, requires root)
```bash
# Comprehensive test with eBPF tracers (60 seconds)
chmod +x scripts/test_pipeline_e2e.sh
sudo ./scripts/test_pipeline_e2e.sh
```

**See detailed testing guide**: [docs/testing/LINUX_VM_TEST.md](docs/testing/LINUX_VM_TEST.md)

## 📚 Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Telemetry Collection](src/telemetry/README.md)
- [Data Pipeline](docs/pipeline/DATA_PIPELINE.md)
- **[Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)** - **NEW: Complete System Setup**
- [Gemini 3 Integration](docs/architecture/GEMINI3_INTEGRATION.md)
- [Development Setup](docs/development/building.md)
- [Testing Guide](docs/testing/LINUX_VM_TEST.md)
- [Quick Reference](docs/testing/QUICK_REFERENCE.md)

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|--------------|
| Collection | C/C++, eBPF, libbpf, perf |
| Pipeline | C++, Python, SQLite, Pandas, NumPy |
| ML Models | Python, scikit-learn, Prophet, Isolation Forest |
| Agent | Python, Google Gemini 3 API |
| CLI | Python, Rich, Click |
| GUI | FastAPI, Plotly.js, HTML/CSS |
| Testing | pytest, Valgrind, mock frameworks |

## 📁 Project Structure

```
KernelSight AI/
├── src/                    # Source code
│   ├── telemetry/         # eBPF tracers and scrapers (C/C++)
│   ├── pipeline/          # Data processing and ingestion
│   ├── agent/             # Gemini AI autonomous agent
│   └── analysis/          # Trend and baseline analyzers
├── scripts/               # Utility scripts
├── docs/                   # Documentation
├── tests/                  # Test suites
├── start_kernelsight.sh   # Main launcher
└── kernelsight            # CLI script
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## 📝 License

See [LICENSE](LICENSE) for details.

## 🔗 Links

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](<issue-tracker-url>)
- Discussions: [GitHub Discussions](<discussions-url>)

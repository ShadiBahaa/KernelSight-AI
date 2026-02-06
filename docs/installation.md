# Installation Guide

## Prerequisites

### System Requirements
- **OS**: Linux kernel 5.15+ (Ubuntu 22.04+ LTS recommended) or WSL2
- **Python**: 3.9 or higher
- **Build Tools**: CMake 3.20+, GCC/Clang
- **Kernel Headers**: Required for eBPF compilation

### Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-venv \
    build-essential cmake \
    linux-headers-$(uname -r) \
    libbpf-dev \
    clang llvm
```

**Fedora/RHEL:**
```bash
sudo dnf install -y \
    python3 python3-pip \
    cmake gcc clang \
    kernel-devel \
    libbpf-devel
```

## Quick Installation

### Option 1: Automated Setup (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/kernelsight-ai.git
cd kernelsight-ai

# Build eBPF tracers
./scripts/build.sh

# Run system (auto-creates venv, installs Python deps)
sudo python3 run_kernelsight.py
```

The orchestrator will:
1. ✅ Auto-create virtual environment
2. ✅ Install all Python dependencies
3. ✅ Prompt for Gemini API key (optional)
4. ✅ Set up database schema
5. ✅ Start all services

### Option 2: Manual Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/kernelsight-ai.git
cd kernelsight-ai

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `. venv/bin/activate`

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Build eBPF tracers
mkdir build && cd build
cmake .. -DBUILD_EBPF=ON
make -j$(nproc)
cd ..

# 5. Run system
sudo -E env PATH=$PATH python3 run_kernelsight.py
```

## Configuration

### Gemini API Key (Optional)

For AI-powered reasoning:

```bash
# Set environment variable
export GEMINI_API_KEY="your-api-key-here"

# Or add to shell profile
echo 'export GEMINI_API_KEY="your-api-key"' >> ~/.bashrc
```

Get your API key at: https://makersuite.google.com/

### Custom Configuration

Edit `config.yaml`:

```yaml
agent:
  cycle_interval_seconds: 60  # Agent decision frequency
  
  actions:
    dry_run: false  # Set true to preview actions without executing
```

## Verify Installation

```bash
# Check database
sqlite3 data/kernelsight.db "SELECT COUNT(*) FROM signal_metadata;"

# Query signals
python3 kernelsight query --limit 5

# Run diagnostics
python3 kernelsight diagnostics
```

## Troubleshooting

### eBPF Build Fails

**Issue**: `Could not find libbpf`

**Solution**:
```bash
sudo apt install libbpf-dev linux-headers-$(uname -r)
```

### Permission Denied

**Issue**: eBPF programs require root

**Solution**: Run with `sudo`
```bash
sudo python3 run_kernelsight.py
```

### Virtual Environment Issues

**Issue**: `venv` creation fails

**Solution**:
```bash
# Use system Python
sudo python3 run_kernelsight.py

# Or manually create venv
python3 -m venv ~/kernelsight-venv
source ~/kernelsight-venv/bin/activate
```

## Next Steps

- [Quick Start Guide](quickstart.md)
- [CLI Reference](CLI_REFERENCE.md)
- [Web Dashboard](WEB_DASHBOARD.md)
- [Testing](TESTING.md)

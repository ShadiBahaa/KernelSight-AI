# Development Setup

This guide will help you set up a development environment for KernelSight AI.

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+ or equivalent)
- **Kernel**: 5.15+ with eBPF support
- **Architecture**: x86_64 or ARM64

### Required Tools

```bash
# Build tools
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    clang \
    llvm \
    git

# eBPF dependencies
sudo apt-get install -y \
    libbpf-dev \
    linux-headers-$(uname -r) \
    bpftool

# Python
sudo apt-get install -y \
    python3.9 \
    python3.9-dev \
    python3-pip \
    python3-venv
```

## Setup Steps

### 1. Clone Repository

```bash
git clone <repository-url>
cd "KernelSight AI"
```

### 2. Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Environment

```bash
# Create .env file
cat > .env << EOF
GEMINI_API_KEY=your_api_key_here
DATABASE_PATH=./data/kernelsight.db
LOG_LEVEL=DEBUG
EOF
```

### 4. Build C/C++ Components

```bash
mkdir -p build
cd build
cmake ..
make

# Verify build
./telemetry/collector --version  # (placeholder, will be implemented)
```

### 5. Verify eBPF Support

```bash
# Check kernel version
uname -r  # Should be 5.15+

# Check BPF filesystem
mount | grep bpf

# Try loading a simple BPF program (requires root)
sudo bpftool prog list
```

## Development Workflow

### Code Formatting

```bash
# Python
black src/
flake8 src/

# C/C++
find src/telemetry -name "*.c" -o -name "*.cpp" | xargs clang-format -i
```

### Type Checking

```bash
mypy src/
```

### Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_ml/

# With coverage
pytest --cov=src --cov-report=html
```

### Interactive Development

```bash
# IPython with project context
ipython

# Example: Test metric query
from src.pipeline.api import MetricAPI
api = MetricAPI()
metrics = api.query("cpu.util.user", last_minutes=5)
```

## IDE Setup

### VS Code (Recommended)

Install extensions:
- Python (Microsoft)
- C/C++ (Microsoft)
- CMake Tools
- eBPF for Visual Studio Code

Workspace settings:
```json
{
    "python.linting.enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "C_Cpp.clang_format_style": "file"
}
```

## Troubleshooting

### eBPF Programs Won't Load

```bash
# Check kernel config
zgrep CONFIG_BPF /proc/config.gz

# Verify BPF filesystem
sudo mount -t bpf bpf /sys/fs/bpf
```

### Python Dependencies Failing

```bash
# Update pip
pip install --upgrade pip setuptools wheel

# Install with verbose output
pip install -v -r requirements.txt
```

## Next Steps

- Read [Architecture Overview](../architecture/overview.md)
- Review [Telemetry Metrics Specification](../telemetry/metrics-spec.md)
- Check [Building Guide](building.md) for advanced build options

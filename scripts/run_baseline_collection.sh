#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
#
# Baseline Collection (No Stress)
# Runs collectors without stress workload to capture normal system behavior

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

DURATION=${1:-3600}  # Default: 1 hour

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   KernelSight AI - Baseline Collection                      ║"
echo "║   Normal Operation Data (No Stress Workload)                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${YELLOW}This script requires root privileges for eBPF tracers.${NC}"
    echo "Restarting with sudo..."
    exec sudo "$0" "$@"
fi

echo -e "${BLUE}Configuration:${NC}"
echo "  Duration: $((DURATION / 60)) minutes ($DURATION seconds)"
echo "  Database: data/baseline.db"
echo "  Logs: logs/baseline/"
echo "  Mode: No stress workload (baseline only)"
echo ""
echo -e "${YELLOW}This will collect normal system behavior for baseline learning.${NC}"
echo ""

read -p "Press Enter to start baseline collection, or Ctrl+C to cancel... "

# Prepare directories
mkdir -p logs/baseline
rm -f data/baseline.db*

echo -e "\n${GREEN}Initializing database...${NC}"
python3 src/pipeline/ingestion_daemon.py --init-only --db-path data/baseline.db

echo -e "${GREEN}Starting collectors (no stress workload)...${NC}\n"

# Start ingestion daemon
rm -f /tmp/kernelsight_baseline
mkfifo /tmp/kernelsight_baseline

python3 src/pipeline/ingestion_daemon.py \
    --db-path data/baseline.db \
    --batch-size 100 \
    --batch-timeout 1.0 \
    --verbose \
    < /tmp/kernelsight_baseline \
    > logs/baseline/ingestion.log 2>&1 &
INGESTION_PID=$!
echo "Ingestion daemon started (PID: $INGESTION_PID)"

sleep 2

# Start scraper daemon
./build/src/telemetry/scraper_daemon \
    2>> logs/baseline/scraper.log \
    >> /tmp/kernelsight_baseline &
SCRAPER_PID=$!
echo "Scraper daemon started (PID: $SCRAPER_PID)"

# Start eBPF tracers (from build directory)
cd build/src/telemetry 2>/dev/null || {
    echo -e "${YELLOW}Warning: build/src/telemetry/ not found, skipping eBPF tracers${NC}"
}

if [[ -f "syscall_tracer" && -f "syscall_tracer.bpf.o" ]]; then
    ./syscall_tracer 2>> ../../../logs/baseline/syscall.log >> /tmp/kernelsight_baseline &
    echo "Syscall tracer started (PID: $!)"
fi

if [[ -f "io_latency_tracer" && -f "io_latency_tracer.bpf.o" ]]; then
    ./io_latency_tracer 2>> ../../../logs/baseline/io.log >> /tmp/kernelsight_baseline &
    echo "I/O latency tracer started (PID: $!)"
fi

if [[ -f "page_fault_tracer" && -f "page_fault_tracer.bpf.o" ]]; then
    ./page_fault_tracer 2>> ../../../logs/baseline/pagefault.log >> /tmp/kernelsight_baseline &
    echo "Page fault tracer started (PID: $!)"
fi

if [[ -f "sched_tracer" && -f "sched_tracer.bpf.o" ]]; then
    ./sched_tracer 2>> ../../../logs/baseline/sched.log >> /tmp/kernelsight_baseline &
    echo "Scheduler tracer started (PID: $!)"
fi

cd - > /dev/null

echo -e "\n${GREEN}Collection in progress...${NC}"
echo -e "${BLUE}Collecting baseline data for $((DURATION / 60)) minutes${NC}\n"

# Progress bar
for ((i=1; i<=DURATION; i++)); do
    PCT=$((i * 100 / DURATION))
    MINS=$((i / 60))
    SECS=$((i % 60))
    echo -ne "\r  Progress: [$(printf '%*s' $((PCT/2)) | tr ' ' '=')$(printf '%*s' $((50-PCT/2)))] ${MINS}m ${SECS}s / $((DURATION/60))m"
    sleep 1
done

echo -e "\n\n${GREEN}Baseline collection complete!${NC}"

# Cleanup
echo "Stopping collectors..."
kill $SCRAPER_PID $INGESTION_PID 2>/dev/null || true
pkill -f "syscall_tracer" 2>/dev/null || true
pkill -f "io_latency_tracer" 2>/dev/null || true
pkill -f "page_fault_tracer" 2>/dev/null || true
pkill -f "sched_tracer" 2>/dev/null || true
rm -f /tmp/kernelsight_baseline

sleep 2

# Show results
echo -e "\n${BLUE}Collection Results:${NC}"
python3 << 'PYEOF'
import sys
sys.path.insert(0, 'src/pipeline')
from db_manager import DatabaseManager

db = DatabaseManager('data/baseline.db')
stats = db.get_table_stats()
total = sum(v for v in stats.values() if v > 0)

print(f"Total events: {total:,}")
print("\nEvent breakdown:")
for table, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
    if count > 0:
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {table:30} {count:8,} rows ({pct:5.1f}%)")

db.close()
PYEOF

echo -e "\n${BLUE}Next steps:${NC}"
echo "  1. Learn baseline statistics:"
echo "     python scripts/verify_features.py --db-path data/baseline.db --baseline-mode"
echo ""
echo "  2. Analyze baseline data:"
echo "     python scripts/explore_data.py --database data/baseline.db --output-dir data/reports/baseline"
echo ""
echo "  3. Use for anomaly detection:"
echo "     # Compare new data against this baseline"
echo ""

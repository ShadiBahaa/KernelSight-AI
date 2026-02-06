#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
#
# Comprehensive stress test for KernelSight AI pipeline
# Tests ALL collectors + generates system stress to capture all event types

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TEST_DURATION=${TEST_DURATION:-60}
DB_PATH="data/stress_test.db"
LOG_DIR="logs/stress_test"
PIDS=()

# Cleanup
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    # Kill any remaining stress processes
    pkill -f "stress " 2>/dev/null || true
    pkill -f "dd if=" 2>/dev/null || true
    # Kill HTTP server if still running
    pkill -f "python3 -m http.server 8080" 2>/dev/null || true
    # Remove network stress temp files
    rm -rf /tmp/stress_web 2>/dev/null || true
    # Remove FIFO
    rm -f /tmp/kernelsight_stress 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: This test must run as root (for eBPF tracers)${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   KernelSight AI - Comprehensive Stress Test                ║"
echo "║   All Collectors + System Stress + Full Validation          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Check prerequisites
echo -e "${BLUE}[1/6] Checking Prerequisites${NC}"
for binary in scraper_daemon syscall_tracer io_latency_tracer; do
    if [[ ! -f "build/src/telemetry/$binary" ]]; then
        echo -e "${RED}ERROR: $binary not found${NC}"
        exit 1
    fi
done

# Check for stress tool
if ! command -v stress &> /dev/null; then
    echo -e "${YELLOW}WARNING: 'stress' tool not found. Install with: apt-get install stress${NC}"
    echo "Continuing without stress workload..."
    HAS_STRESS=false
else
    HAS_STRESS=true
fi
echo -e "${GREEN}✓ Prerequisites checked${NC}\n"

# Initialize database
echo -e "${BLUE}[2/6] Initializing Database${NC}"
rm -f "$DB_PATH"*
mkdir -p "$LOG_DIR"
python3 src/pipeline/ingestion_daemon.py --init-only --db-path "$DB_PATH"
echo -e "${GREEN}✓ Database initialized${NC}\n"

# Start ingestion daemon
echo -e "${BLUE}[3/6] Starting Ingestion Daemon${NC}"
rm -f /tmp/kernelsight_stress
mkfifo /tmp/kernelsight_stress

python3 src/pipeline/ingestion_daemon.py \
    --db-path "$DB_PATH" \
    --batch-size 100 \
    --batch-timeout 1.0 \
    --verbose \
    < /tmp/kernelsight_stress \
    > "$LOG_DIR/ingestion.log" 2>&1 &
INGESTION_PID=$!
PIDS+=($INGESTION_PID)
echo "  Ingestion daemon PID: $INGESTION_PID"
sleep 2
echo -e "${GREEN}✓ Ingestion daemon started${NC}\n"

# Start all collectors
echo -e "${BLUE}[4/6] Starting All Collectors${NC}"

# Save current directory
PROJ_DIR=$(pwd)

# Scraper daemon (run from project root)
echo "  Starting scraper_daemon..."
./build/src/telemetry/scraper_daemon 2>> "$LOG_DIR/scraper.log" >> /tmp/kernelsight_stress &
PIDS+=($!)
echo "    PID: $! | Log: $LOG_DIR/scraper.log"

# eBPF tracers need to run from build/src/telemetry/ where .bpf.o files are
cd build/src/telemetry 2>/dev/null || {
    echo -e "${YELLOW}  WARNING: build/src/telemetry/ not found${NC}"
    echo "  eBPF tracers may not work. Run cmake build first."
    cd "$PROJ_DIR"
}

# Syscall tracer
if [[ -f "syscall_tracer" && -f "syscall_tracer.bpf.o" ]]; then
    echo "  Starting syscall_tracer (eBPF)..."
    ./syscall_tracer 2>> "$PROJ_DIR/$LOG_DIR/syscall.log" >> /tmp/kernelsight_stress &
    PIDS+=($!)
    echo "    PID: $! | Log: $LOG_DIR/syscall.log"
else
    echo -e "${YELLOW}  Skipping syscall_tracer (not found or .bpf.o missing)${NC}"
fi

# I/O latency tracer
if [[ -f "io_latency_tracer" && -f "io_latency_tracer.bpf.o" ]]; then
    echo "  Starting io_latency_tracer (eBPF)..."
    ./io_latency_tracer 2>> "$PROJ_DIR/$LOG_DIR/io.log" >> /tmp/kernelsight_stress &
    PIDS+=($!)
    echo "    PID: $! | Log: $LOG_DIR/io.log"
else
    echo -e "${YELLOW}  Skipping io_latency_tracer (not found or .bpf.o missing)${NC}"
fi

# Page fault tracer
if [[ -f "page_fault_tracer" && -f "page_fault_tracer.bpf.o" ]]; then
    echo "  Starting page_fault_tracer (eBPF)..."
    ./page_fault_tracer 2>> "$PROJ_DIR/$LOG_DIR/pagefault.log" >> /tmp/kernelsight_stress &
    PIDS+=($!)
    echo "    PID: $! | Log: $LOG_DIR/pagefault.log"
else
    echo -e "${YELLOW}  Skipping page_fault_tracer (not found or .bpf.o missing)${NC}"
fi

# Scheduler tracer
if [[ -f "sched_tracer" && -f "sched_tracer.bpf.o" ]]; then
    echo "  Starting sched_tracer (eBPF)..."
    ./sched_tracer 2>> "$PROJ_DIR/$LOG_DIR/sched.log" >> /tmp/kernelsight_stress &
    PIDS+=($!)
    echo "    PID: $! | Log: $LOG_DIR/sched.log"
else
    echo -e "${YELLOW}  Skipping sched_tracer (not found or .bpf.o missing)${NC}"
fi

# Return to project directory
cd "$PROJ_DIR"

sleep 3
echo -e "${GREEN}✓ All collectors started${NC}\n"

# Generate system stress
echo -e "${BLUE}[5/6] Generating System Stress (${TEST_DURATION}s)${NC}"
echo "  Workloads running in background..."

if [[ "$HAS_STRESS" == true ]]; then
    # CPU stress
    echo "    - CPU stress (4 workers)"
    stress --cpu 4 --timeout ${TEST_DURATION}s > /dev/null 2>&1 &
    
    # Memory stress
    echo "    - Memory stress (1GB)"
    stress --vm 2 --vm-bytes 512M --timeout ${TEST_DURATION}s > /dev/null 2>&1 &
    
    # I/O stress
    echo "    - I/O stress"
    stress --io 4 --timeout ${TEST_DURATION}s > /dev/null 2>&1 &
fi

# Additional I/O workload (doesn't require stress tool)
echo "    - Heavy disk I/O"
(
    for i in {1..5}; do
        dd if=/dev/zero of=/tmp/stress_$i.tmp bs=1M count=100 2>/dev/null
        cat /tmp/stress_$i.tmp > /dev/null
        rm -f /tmp/stress_$i.tmp
    done
) > /dev/null 2>&1 &

# File system operations (triggers syscalls)
echo "    - File system operations"
(
    find /usr/share -type f 2>/dev/null | head -1000 | while read f; do
        cat "$f" > /dev/null 2>&1
    done
) &

# Network stress - HTTP server and client workload
echo "    - Network stress (HTTP server + client)"
mkdir -p /tmp/stress_web
echo "Network stress test content" > /tmp/stress_web/index.html
echo "More test data for HTTP transfers" > /tmp/stress_web/test.txt

# Start simple HTTP server on localhost:8080
python3 -m http.server 8080 --directory /tmp/stress_web > /dev/null 2>&1 &
HTTP_SERVER_PID=$!
PIDS+=($HTTP_SERVER_PID)
sleep 1  # Give server time to start

# HTTP client workload - generates TCP connections
echo "    - HTTP client requests"
(
    # Make repeated HTTP requests to create TCP connections
    for i in {1..150}; do
        curl -s http://localhost:8080/ > /dev/null 2>&1
        curl -s http://localhost:8080/test.txt > /dev/null 2>&1
        sleep 0.1  # Small delay to create varied connection states
    done
) &

# TCP connection bursts - creates many short-lived connections
echo "    - TCP connection bursts"
python3 << 'PYEOF' &
import socket
import time
import sys

# Suppress any errors
sys.stderr = open('/dev/null', 'w')

for i in range(100):
    try:
        # Create short-lived TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(('localhost', 8080))
        
        # Send minimal HTTP request
        sock.send(b'GET / HTTP/1.0\r\n\r\n')
        
        # Close immediately to populate TIME_WAIT states
        sock.close()
        
        time.sleep(0.15)
    except:
        pass
PYEOF


# Progress bar
echo ""
for ((i=1; i<=TEST_DURATION; i++)); do
    PCT=$((i * 100 / TEST_DURATION))
    echo -ne "\r  Progress: [$(printf '%*s' $((PCT/2)) | tr ' ' '=')$(printf '%*s' $((50-PCT/2)))] ${i}/${TEST_DURATION}s"
    sleep 1
done
echo ""

echo -e "${GREEN}✓ Stress test complete${NC}\n"

# Stop collectors
echo -e "${BLUE}[6/6] Stopping Collectors & Analyzing Results${NC}"
cleanup

echo "Waiting for ingestion to flush..."
sleep 3

# Analyze results
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    TEST RESULTS                           ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

python3 << 'PYEOF'
import sys
sys.path.insert(0, 'src/pipeline')
from db_manager import DatabaseManager

db = DatabaseManager('data/stress_test.db')
stats = db.get_table_stats()
total = sum(v for v in stats.values() if v > 0)

# Define expected event types
expected_types = {
    'syscall_events': 'eBPF Syscall Tracer',
    'page_fault_events': 'eBPF Page Fault Tracer',
    'io_latency_stats': 'eBPF I/O Latency Tracer',
    'sched_events': 'eBPF Scheduler Tracer',
    'memory_metrics': 'Scraper Daemon',
    'load_metrics': 'Scraper Daemon',
    'block_stats': 'Scraper Daemon',
    'network_interface_stats': 'Scraper Daemon',
    'tcp_stats': 'Scraper Daemon',
    'tcp_retransmit_stats': 'Scraper Daemon',
}

print(f"Total Events Collected: {total}")
print(f"\nEvent Types Captured:\n")

captured = 0
missing = 0

for table, source in expected_types.items():
    count = stats.get(table, 0)
    if count > 0:
        print(f"  ✓ {table:30} {count:6} rows  ({source})")
        captured += 1
    else:
        print(f"  ✗ {table:30}      0 rows  ({source}) ← NOT CAPTURED")
        missing += 1

print(f"\n{'─' * 60}")
print(f"Captured: {captured}/10 event types")
print(f"Missing:  {missing}/10 event types")

if missing == 0:
    print("\n🎉 SUCCESS! All event types captured!")
elif captured >= 6:
    print(f"\n✓ PARTIAL SUCCESS - {captured} event types captured")
    print("  Missing events likely due to:")
    print("    - eBPF tracers not built/running")
    print("    - Insufficient stress to trigger events")
else:
    print("\n⚠ WARNING - Only {captured} event types captured")

# Show sample data
if stats.get('syscall_events', 0) > 0:
    print("\nSample Slow Syscalls:")
    rows = db.query("""
        SELECT comm, syscall_name, latency_ns / 1000000.0 as latency_ms
        FROM syscall_events 
        ORDER BY latency_ns DESC LIMIT 3
    """)
    for row in rows:
        print(f"  {row['comm']:10} | {row['syscall_name']:10} | {row['latency_ms']:.2f}ms")

if stats.get('page_fault_events', 0) > 0:
    print("\nPage Fault Summary:")
    rows = db.query("""
        SELECT fault_type, COUNT(*) as count, 
               AVG(latency_ns) / 1000.0 as avg_latency_us
        FROM page_fault_events
        GROUP BY fault_type
    """)
    for row in rows:
        print(f"  {row['fault_type']:10} faults: {row['count']:5} (avg: {row['avg_latency_us']:.2f}μs)")

db.close()
PYEOF

echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Test Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo "Database: $DB_PATH"
echo "Logs: $LOG_DIR/"
echo ""
echo "To query the data:"
echo "  python3 src/pipeline/query_utils.py --db-path $DB_PATH --demo"
echo "  sqlite3 $DB_PATH"

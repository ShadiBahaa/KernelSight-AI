#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
#
# 1-Hour Semantic Stress Test
# Tests full pipeline with semantic signal processing

set -e

# Set Python path to project root
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
TEST_DURATION=${TEST_DURATION:-3600}  # 1 hour default
DB_PATH="data/semantic_stress_test.db"
LOG_DIR="logs/semantic_stress_test"
PIDS=()

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   KernelSight AI - 1-Hour Semantic Stress Test                 ║"
echo "║   Full Pipeline: eBPF → Semantic Classifiers → Agent Memory   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

echo -e "${CYAN}Test Duration: $TEST_DURATION seconds ($(($TEST_DURATION/60)) minutes)${NC}\n"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    pkill -f "stress " 2>/dev/null || true
    pkill -f "dd if=" 2>/dev/null || true
    rm -f /tmp/kernelsight_semantic 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# Check root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: Must run as root (for eBPF)${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Initialize database
echo -e "${BLUE}[1/5] Initializing Semantic Database${NC}"
rm -f "$DB_PATH"*
mkdir -p "$LOG_DIR"
python3 src/pipeline/semantic_ingestion_daemon.py --init-only --db-path "$DB_PATH"
echo -e "${GREEN}✓ Database initialized with signal_metadata table${NC}\n"

# Start semantic ingestion daemon
echo -e "${BLUE}[2/5] Starting Semantic Ingestion Daemon${NC}"
rm -f /tmp/kernelsight_semantic
mkfifo /tmp/kernelsight_semantic

python3 src/pipeline/semantic_ingestion_daemon.py \
    --db-path "$DB_PATH" \
    --num-cpus $(nproc) \
    < /tmp/kernelsight_semantic \
    > "$LOG_DIR/semantic_ingestion.log" 2>&1 &
INGESTION_PID=$!
PIDS+=($INGESTION_PID)
echo "  Semantic ingestion daemon PID: $INGESTION_PID"
sleep 2
echo -e "${GREEN}✓ Semantic ingestion running${NC}\n"

# Start all collectors (simplified - using only key ones for demo)
echo -e "${BLUE}[3/5] Starting eBPF Collectors + Scrapers${NC}"

# Syscall tracer (high-latency syscalls)
if [[ -f "build/src/telemetry/syscall_tracer" ]]; then
    cd build/src/telemetry
    sudo ./syscall_tracer 2>> "../../../$LOG_DIR/syscall.log" | \
        jq -c '{type:"syscall"} + .' >> /tmp/kernelsight_semantic &
    PIDS+=($!)
    cd - > /dev/null
    echo "  ✓ Syscall tracer started"
fi

# Scraper daemon (memory, load, network, TCP stats)
if [[ -f "build/src/telemetry/scraper_daemon" ]]; then
    cd build/src/telemetry
    sudo ./scraper_daemon --json 2>> "../../../$LOG_DIR/scraper.log" | \
        ../../../scripts/map_event_types.sh | \
        while read line; do
            # Map types and route to semantic daemon
            echo "$line" >> /tmp/kernelsight_semantic
        done &
    PIDS+=($!)
    cd - > /dev/null
    echo "  ✓ Scraper daemon started (memory, load, network, TCP)"
fi

sleep 3
echo -e "${GREEN}✓ All collectors running${NC}\n"

# Start system stress
echo -e "${BLUE}[4/5] Starting System Stress Workload${NC}"

if command -v stress &> /dev/null; then
    # CPU stress - light (1 worker to avoid hanging)
    stress --cpu 1 --timeout ${TEST_DURATION}s &
    PIDS+=($!)
    echo "  ✓ CPU stress (1 worker - light load)"
    
    # Memory stress - light 1GB (~12% on 8GB system, safe for VM)
    stress --vm 1 --vm-bytes 1000M --timeout ${TEST_DURATION}s &
    PIDS+=($!)
    echo "  ✓ Memory stress (1GB - light load)"
    
    # I/O stress - light
    stress --io 2 --timeout ${TEST_DURATION}s &
    PIDS+=($!)
    echo "  ✓ I/O stress (2 workers - light load)"
else
    echo -e "${YELLOW}  ⚠ 'stress' not found - baseline collection only${NC}"
fi

echo -e "${GREEN}✓ Stress workload running${NC}\n"

# Monitor progress
echo -e "${BLUE}[5/5] Running Test${NC}"
echo -e "${CYAN}Duration: $(($TEST_DURATION/60)) minutes${NC}"
echo -e "${CYAN}Database: $DB_PATH${NC}"
echo -e "${CYAN}Logs: $LOG_DIR/${NC}\n"

echo "Monitoring progress (Ctrl+C to stop early)..."

START_TIME=$(date +%s)
echo "[DEBUG] Test started at timestamp: $START_TIME"

LAST_SHOWN=0
while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$(($CURRENT_TIME - START_TIME))
    REMAINING=$(($TEST_DURATION - ELAPSED))
    
    if [[ $REMAINING -le 0 ]]; then
        break
    fi
    
    # Show progress every minute, but show immediately on startup
    CURRENT_MINUTE=$(($ELAPSED / 60))
    if [[ $CURRENT_MINUTE -gt $LAST_SHOWN ]] || [[ $ELAPSED -eq 0 ]]; then
        LAST_SHOWN=$CURRENT_MINUTE
        if [[ $CURRENT_MINUTE -eq 0 ]]; then
            echo -e "${CYAN}  Starting test... (monitoring every 60 seconds)${NC}"
        else
            echo -e "${CYAN}  [$CURRENT_MINUTE min] Test in progress... ($REMAINING seconds remaining)${NC}"
        fi
        
        # Show quick stats using python (more reliable than sqlite3 binary)
        if [[ -f "$DB_PATH" ]]; then
            python3 -c "import sqlite3; conn=sqlite3.connect('$DB_PATH'); print('    Raw events:', conn.execute('SELECT COUNT(*) FROM syscall_events').fetchone()[0], '| Semantic signals:', conn.execute('SELECT COUNT(*) FROM signal_metadata').fetchone()[0]); conn.close()" 2>/dev/null || echo "    (Stats temporarily unavailable)"
        fi
    fi
    
    sleep 5
done

echo -e "\n${GREEN}✓ Test completed!${NC}\n"

# Final statistics
echo -e "${BLUE}═══════════════════ Final Statistics  ═══════════════════${NC}"

if [[ -f "$DB_PATH" ]]; then
    echo -e "\n${CYAN}Raw Event Counts:${NC}"
    sqlite3 "$DB_PATH" <<EOF
SELECT 
    'Syscall Events: ' || COUNT(*) FROM syscall_events
UNION ALL SELECT 'Sched Events: ' || COUNT(*) FROM sched_events
UNION ALL SELECT 'Memory Metrics: ' || COUNT(*) FROM memory_metrics
UNION ALL SELECT 'Load Metrics: ' || COUNT(*) FROM load_metrics
UNION ALL SELECT 'I/O Stats: ' || COUNT(*) FROM io_latency_stats
UNION ALL SELECT 'Block Stats: ' || COUNT(*) FROM block_stats
UNION ALL SELECT 'Network Stats: ' || COUNT(*) FROM network_interface_stats
UNION ALL SELECT 'TCP Stats: ' || COUNT(*) FROM tcp_stats
UNION ALL SELECT 'Page Faults: ' || COUNT(*) FROM page_fault_events;
EOF

    echo -e "\n${GREEN}Semantic Signal Counts:${NC}"
    sqlite3 "$DB_PATH" <<EOF
SELECT 
    signal_type || ': ' || COUNT(*) as count
FROM signal_metadata
GROUP BY signal_type
ORDER BY COUNT(*) DESC;
EOF

    echo -e "\n${GREEN}Severity Distribution:${NC}"
    sqlite3 "$DB_PATH" <<EOF
SELECT 
    severity || ': ' || COUNT(*) as count
FROM signal_metadata
GROUP BY severity
ORDER BY 
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END;
EOF

    echo -e "\n${CYAN}Sample Observations (Top 5 Critical/High):${NC}"
    sqlite3 "$DB_PATH" <<EOF
.mode column
.headers on
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    signal_type,
    severity,
    summary
FROM signal_metadata
WHERE severity IN ('critical', 'high')
ORDER BY timestamp DESC
LIMIT 5;
EOF
fi

echo -e "\n${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Test completed successfully!${NC}"

# Run automatic analysis
echo -e "\n${BLUE}═══════════════════ Running Analysis  ═══════════════════${NC}"
echo -e "${CYAN}Generating visualizations and reports...${NC}\n"

python3 scripts/analyze_semantic_signals.py "$DB_PATH" --output "reports/semantic_stress_$(date +%Y%m%d_%H%M%S)"

echo -e "\n${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}Next steps:${NC}"
echo -e "  1. View plots: ls -lt reports/semantic_stress_*/  "
echo -e "  2. Read report: cat reports/semantic_stress_*/analysis_report.txt"
echo -e "  3. Query database: sqlite3 $DB_PATH"
echo -e "  4. View logs: ls -lh $LOG_DIR/"
echo ""


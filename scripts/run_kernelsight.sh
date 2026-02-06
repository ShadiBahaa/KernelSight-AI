#!/bin/bash
# KernelSight AI - Production Orchestration Script
# Copyright (c) 2025 KernelSight AI
#
# This is the MAIN script to run the complete KernelSight AI system.
# It coordinates:
#   1. eBPF tracers (syscall, scheduler, page_fault, io_latency)
#   2. System metrics scraper
#   3. Semantic ingestion daemon (raw data → semantic signals)
#   4. Autonomous agent (monitors signals → takes actions)
#
# Usage:
#   ./run_kernelsight.sh                    - Run full system in tmux
#   ./run_kernelsight.sh --db <path>        - Specify database path
#   ./run_kernelsight.sh --no-agent         - Run without autonomous agent
#   ./run_kernelsight.sh --agent-interval N - Agent check interval in seconds (default: 60)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default configuration
DB_PATH="$PROJECT_ROOT/data/kernelsight.db"
RUN_AGENT=true
AGENT_INTERVAL=60  # Agent check interval in seconds
NO_HUMAN=false     # Require user approval for actions (default: ask for approval)
TMUX_SESSION="kernelsight"
LOG_DIR="$PROJECT_ROOT/logs/production"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            DB_PATH="$2"
            shift 2
            ;;
        --no-agent)
            RUN_AGENT=false
            shift
            ;;
        --agent-interval)
            AGENT_INTERVAL="$2"
            shift 2
            ;;
        --no-human)
            NO_HUMAN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --db PATH            Database file path (default: data/kernelsight.db)"
            echo "  --no-agent           Run without autonomous agent"
            echo "  --agent-interval N   Agent check interval in seconds (default: 60)"
            echo "  --no-human           Fully autonomous mode - NO user approval needed"
            echo "  --help               Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done


echo -e "${BLUE}=========================================="
echo "KernelSight AI - Production System"
echo -e "==========================================${NC}"
echo ""

# Verify build artifacts exist
echo -e "${BLUE}→ Verifying build artifacts...${NC}"

BUILD_DIR="$PROJECT_ROOT/build/src/telemetry"
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}✗ Build directory not found: $BUILD_DIR${NC}"
    echo "  Please run: cd $PROJECT_ROOT && mkdir -p build && cd build && cmake .. && make"
    exit 1
fi

SYSCALL_BIN="$BUILD_DIR/syscall_tracer"
SCHED_BIN="$BUILD_DIR/sched_tracer"
PAGEFAULT_BIN="$BUILD_DIR/page_fault_tracer"
IO_BIN="$BUILD_DIR/io_latency_tracer"
SCRAPER_BIN="$BUILD_DIR/scraper_daemon"

MISSING_BINS=()
[ ! -f "$SYSCALL_BIN" ] && MISSING_BINS+=("syscall_tracer")
[ ! -f "$SCHED_BIN" ] && MISSING_BINS+=("sched_tracer")
[ ! -f "$PAGEFAULT_BIN" ] && MISSING_BINS+=("page_fault_tracer")
[ ! -f "$IO_BIN" ] && MISSING_BINS+=("io_latency_tracer")
[ ! -f "$SCRAPER_BIN" ] && MISSING_BINS+=("scraper_daemon")

if [ ${#MISSING_BINS[@]} -gt 0 ]; then
    echo -e "${RED}✗ Missing binaries: ${MISSING_BINS[@]}${NC}"
    echo "  Please build the project first"
    exit 1
fi

echo -e "${GREEN}✓ All binaries found${NC}"

# Check Python dependencies
echo -e "${BLUE}→ Verifying Python environment...${NC}"

if ! python3 -c "import sqlite3" 2>/dev/null; then
    echo -e "${RED}✗ Python sqlite3 module not available${NC}"
    exit 1
fi

SEMANTIC_DAEMON="$PROJECT_ROOT/src/pipeline/semantic_ingestion_daemon.py"
AGENT_SCRIPT="$PROJECT_ROOT/src/agent/autonomous_loop.py"

if [ ! -f "$SEMANTIC_DAEMON" ]; then
    echo -e "${RED}✗ Semantic ingestion daemon not found: $SEMANTIC_DAEMON${NC}"
    exit 1
fi

if [ "$RUN_AGENT" = true ] && [ ! -f "$AGENT_SCRIPT" ]; then
    echo -e "${RED}✗ Autonomous agent script not found: $AGENT_SCRIPT${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python environment ready${NC}"

# Initialize database
echo -e "${BLUE}→ Initializing database...${NC}"
mkdir -p "$(dirname "$DB_PATH")"

python3 "$SEMANTIC_DAEMON" --db-path "$DB_PATH" --init-only

echo -e "${GREEN}✓ Database initialized: $DB_PATH${NC}"

# Create log directory
mkdir -p "$LOG_DIR"

echo -e "${BLUE}→ Log directory: $LOG_DIR${NC}"

# Check if session already exists
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Tmux session '$TMUX_SESSION' already exists${NC}"
    read -p "Kill existing session and start fresh? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$TMUX_SESSION"
    else
        echo "Exiting. Use: tmux attach -t $TMUX_SESSION"
        exit 0
    fi
fi

echo ""
echo -e "${BLUE}=========================================="
echo "Starting KernelSight AI System"
echo -e "==========================================${NC}"
echo ""

# Create event directory for data flow (each source writes to its own file)
EVENT_DIR="/tmp/kernelsight_$$"
mkdir -p "$EVENT_DIR"

# Create empty event files for each source
SYSCALL_EVENTS="$EVENT_DIR/syscall.jsonl"
SCHED_EVENTS="$EVENT_DIR/sched.jsonl"
PAGEFAULT_EVENTS="$EVENT_DIR/pagefault.jsonl"
IO_EVENTS="$EVENT_DIR/io.jsonl"
SCRAPER_EVENTS="$EVENT_DIR/scraper.jsonl"
touch "$SYSCALL_EVENTS" "$SCHED_EVENTS" "$PAGEFAULT_EVENTS" "$IO_EVENTS" "$SCRAPER_EVENTS"

echo -e "${BLUE}→ Created event directory: $EVENT_DIR${NC}"
echo -e "${BLUE}→ Each source writes to its own file (no interleaving)${NC}"


# Start tmux session with all components
echo -e "${GREEN}🚀 Launching components in tmux session '$TMUX_SESSION'...${NC}"
echo ""

cd "$BUILD_DIR"

# Window 0: Semantic Ingestion Daemon 
# Uses --watch-files mode to read directly from log files (avoids tail interleaving)
echo "  [0] Semantic Ingestion Daemon"
tmux new-session -d -s "$TMUX_SESSION" -n "ingestion" \
    "echo 'Semantic Ingestion Daemon - Processing events from all sources...'; \
     python3 '$SEMANTIC_DAEMON' --db-path '$DB_PATH' \
       --watch-files '$LOG_DIR/syscall.log' '$LOG_DIR/scheduler.log' '$LOG_DIR/pagefault.log' '$LOG_DIR/io.log' '$LOG_DIR/scraper.log' \
       2>&1 | tee '$LOG_DIR/ingestion.log'"


# Window 1: Syscall Tracer (writes to its own file)
echo "  [1] Syscall Tracer"
tmux new-window -t "$TMUX_SESSION:1" -n "syscall" \
    "echo 'Syscall Tracer - Monitoring high-latency syscalls...'; \
     sudo stdbuf -oL ./syscall_tracer 2>'$LOG_DIR/syscall_err.log' | stdbuf -oL tee '$LOG_DIR/syscall.log' >> '$SYSCALL_EVENTS'"

# Window 2: Scheduler Tracer
echo "  [2] Scheduler Tracer"
tmux new-window -t "$TMUX_SESSION:2" -n "scheduler" \
    "echo 'Scheduler Tracer - Monitoring context switches...'; \
     sudo stdbuf -oL ./sched_tracer 2>'$LOG_DIR/scheduler_err.log' | stdbuf -oL tee '$LOG_DIR/scheduler.log' >> '$SCHED_EVENTS'"

# Window 3: Page Fault Tracer
echo "  [3] Page Fault Tracer"
tmux new-window -t "$TMUX_SESSION:3" -n "pagefault" \
    "echo 'Page Fault Tracer - Monitoring memory faults...'; \
     sudo stdbuf -oL ./page_fault_tracer 2>'$LOG_DIR/pagefault_err.log' | stdbuf -oL tee '$LOG_DIR/pagefault.log' >> '$PAGEFAULT_EVENTS'"

# Window 4: I/O Latency Tracer
echo "  [4] I/O Latency Tracer"
tmux new-window -t "$TMUX_SESSION:4" -n "io" \
    "echo 'I/O Latency Tracer - Monitoring disk I/O...'; \
     sudo stdbuf -oL ./io_latency_tracer 2>'$LOG_DIR/io_err.log' | stdbuf -oL tee '$LOG_DIR/io.log' >> '$IO_EVENTS'"

# Window 5: Scraper Daemon
echo "  [5] Scraper Daemon"
tmux new-window -t "$TMUX_SESSION:5" -n "scraper" \
    "echo 'Scraper Daemon - Collecting system metrics...'; \
     stdbuf -oL ./scraper_daemon 2>'$LOG_DIR/scraper_err.log' | stdbuf -oL tee '$LOG_DIR/scraper.log' >> '$SCRAPER_EVENTS'"


# Window 6: Autonomous Agent Loop (if enabled) - Runs automatically
if [ "$RUN_AGENT" = true ]; then
    if [ "$NO_HUMAN" = true ]; then
        echo "  [6] Autonomous Loop (interval: ${AGENT_INTERVAL}s) ⚠️  NO-HUMAN MODE"
    else
        echo "  [6] Autonomous Loop (interval: ${AGENT_INTERVAL}s) 🛡️  User approval required"
    fi
    
    # Create a simple autonomous loop script
    AGENT_LOOP_SCRIPT="$LOG_DIR/run_autonomous_loop.py"
    cat > "$AGENT_LOOP_SCRIPT" << 'AGENT_SCRIPT'
#!/usr/bin/env python3
import sys
import time
import logging
import os

# Setup path
sys.path.insert(0, os.environ.get('PROJECT_ROOT', '.'))

from src.agent.autonomous_loop import AutonomousAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', 'data/kernelsight.db')
INTERVAL = int(os.environ.get('AGENT_INTERVAL', '60'))
NO_HUMAN = os.environ.get('NO_HUMAN', 'false').lower() == 'true'

logger.info('=== KernelSight AI Autonomous Loop ===')
logger.info(f'Database: {DB_PATH}')
logger.info(f'Check Interval: {INTERVAL}s')
if NO_HUMAN:
    logger.warning('⚠️  NO-HUMAN MODE: Actions will execute WITHOUT user approval!')
else:
    logger.info('🛡️  User approval required before executing actions')

# Create agent with require_approval based on NO_HUMAN flag
agent = AutonomousAgent(DB_PATH, require_approval=not NO_HUMAN)
iteration = 0

try:
    while True:
        iteration += 1
        logger.info(f'[Iteration {iteration}] Starting autonomous analysis...')
        try:
            result = agent.analyze_and_act(max_iterations=3)
            logger.info(f'Status: {result.get("status")}')
            logger.info(f'Action taken: {result.get("action_taken")}')
        except Exception as e:
            logger.error(f'Error: {e}')
        logger.info(f'Sleeping for {INTERVAL}s...')
        time.sleep(INTERVAL)
except KeyboardInterrupt:
    logger.info('Agent stopped')
finally:
    agent.close()
AGENT_SCRIPT

    tmux new-window -t "$TMUX_SESSION:6" -n "auto-loop" \
        "cd '$PROJECT_ROOT' && \
         source ~/kernelsight-venv/bin/activate && \
         export PROJECT_ROOT='$PROJECT_ROOT' && \
         export DB_PATH='$DB_PATH' && \
         export AGENT_INTERVAL='$AGENT_INTERVAL' && \
         export NO_HUMAN='$NO_HUMAN' && \

         python3 '$AGENT_LOOP_SCRIPT' 2>&1 | tee '$LOG_DIR/autonomous_loop.log'"

    # Window 7: Interactive Agent (for manual queries with Gemini)
    echo "  [7] Interactive Agent (Gemini-powered)"
    tmux new-window -t "$TMUX_SESSION:7" -n "interactive" \
        "cd '$PROJECT_ROOT' && \
         source ~/kernelsight-venv/bin/activate && \
         echo '=== KernelSight AI Interactive Agent ===' && \
         echo 'Database: $DB_PATH' && \
         echo '' && \
         python3 interactive_agent.py --db '$DB_PATH' 2>&1 | tee '$LOG_DIR/interactive_agent.log'"
fi

# Select the ingestion window by default
tmux select-window -t "$TMUX_SESSION:0"


echo ""
echo -e "${GREEN}=========================================="
echo "✓ KernelSight AI System Started!"
echo -e "==========================================${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Database: $DB_PATH"
echo "  Logs: $LOG_DIR"
echo "  Tmux Session: $TMUX_SESSION"
if [ "$RUN_AGENT" = true ]; then
    echo "  Agent Interval: ${AGENT_INTERVAL}s"
fi
echo ""

echo -e "${BLUE}Running Components:${NC}"
echo "  [0] Semantic Ingestion - Processes raw events → semantic signals"
echo "  [1] Syscall Tracer     - eBPF monitoring of system calls"
echo "  [2] Scheduler Tracer   - eBPF monitoring of context switches"
echo "  [3] Page Fault Tracer  - eBPF monitoring of memory faults"
echo "  [4] I/O Latency Tracer - eBPF monitoring of disk I/O"
echo "  [5] Scraper Daemon     - System metrics collection"
if [ "$RUN_AGENT" = true ]; then
    echo "  [6] Autonomous Loop    - Auto-runs every ${AGENT_INTERVAL}s (rule-based)"
    echo "  [7] Interactive Agent  - Gemini-powered chat interface"
fi
echo ""

echo -e "${BLUE}Tmux Controls:${NC}"
echo "  Attach to session:   tmux attach -t $TMUX_SESSION"
echo "  Switch windows:      Ctrl+B then 0-7"
echo "  Detach:              Ctrl+B then 'd'"
echo "  Kill session:        tmux kill-session -t $TMUX_SESSION"
echo ""

echo -e "${BLUE}Monitoring Commands:${NC}"
echo "  View signals:        sqlite3 '$DB_PATH' 'SELECT * FROM signal_metadata ORDER BY timestamp DESC LIMIT 10;'"
echo "  View agent logs:     tail -f '$LOG_DIR/agent.log'"
echo "  View all logs:       tail -f '$LOG_DIR/*.log'"
echo ""

echo -e "${YELLOW}Press Enter to attach to tmux session, or Ctrl+C to keep running in background${NC}"
read -r

tmux attach -t "$TMUX_SESSION"

#!/bin/bash
# KernelSight AI - GUI Terminal Orchestration Script
# Opens each component in a separate gnome-terminal window for interactive input
#
# Usage:
#   ./start_kernelsight.sh              - Run full system in gnome-terminal windows
#   ./start_kernelsight.sh --no-agent   - Run without autonomous agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"  # Script is now in project root

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
DB_PATH="$PROJECT_ROOT/data/kernelsight.db"
RUN_AGENT=true
AGENT_INTERVAL=60
LOG_DIR="$PROJECT_ROOT/logs/production"
BUILD_DIR="$PROJECT_ROOT/build/src/telemetry"
UNIFIED_MODE=false
LITE_MODE=false

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
        --unified)
            UNIFIED_MODE=true
            shift
            ;;
        --lite)
            LITE_MODE=true
            UNIFIED_MODE=true  # Lite mode implies unified
            shift
            ;;
        --agent-interval)
            AGENT_INTERVAL="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BLUE}=========================================="
echo "KernelSight AI - GUI Terminal Mode"
echo -e "==========================================${NC}"

# =============================================================================
# AUTO-SETUP: Virtual Environment, Requirements, and API Key
# =============================================================================

VENV_DIR="$HOME/kernelsight-venv"  # Use home dir (shared folders don't support symlinks)
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

# Step 1: Check/Create Virtual Environment
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    # Remove broken venv if exists (e.g., Windows venv on Linux)
    if [ -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Removing incompatible venv (cross-platform issue)...${NC}"
        rm -rf "$VENV_DIR"
    fi
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Step 2: Activate Virtual Environment
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Step 3: Check/Install Requirements
if [ -f "$REQUIREMENTS_FILE" ]; then
    # Check if requirements are already installed (using a marker file)
    MARKER_FILE="$VENV_DIR/.requirements_installed"
    REQUIREMENTS_HASH=$(md5sum "$REQUIREMENTS_FILE" 2>/dev/null | cut -d' ' -f1)
    
    if [ ! -f "$MARKER_FILE" ] || [ "$(cat "$MARKER_FILE" 2>/dev/null)" != "$REQUIREMENTS_HASH" ]; then
        echo -e "${YELLOW}Installing Python dependencies...${NC}"
        pip install -q --upgrade pip
        pip install -q -r "$REQUIREMENTS_FILE"
        echo "$REQUIREMENTS_HASH" > "$MARKER_FILE"
        echo -e "${GREEN}✓ Dependencies installed${NC}"
    else
        echo -e "${GREEN}✓ Dependencies already installed${NC}"
    fi
else
    echo -e "${YELLOW}⚠ requirements.txt not found, skipping dependency check${NC}"
fi

# Step 4: Check/Prompt for Gemini API Key
if [ -z "$GEMINI_API_KEY" ]; then
    # Check if there's a saved key
    KEY_FILE="$PROJECT_ROOT/.gemini_api_key"
    if [ -f "$KEY_FILE" ]; then
        export GEMINI_API_KEY=$(cat "$KEY_FILE")
        echo -e "${GREEN}✓ Gemini API key loaded from file${NC}"
    else
        echo ""
        echo -e "${YELLOW}=========================================="
        echo "Gemini API Key Required"
        echo -e "==========================================${NC}"
        echo ""
        echo "Get your API key from: https://aistudio.google.com/apikey"
        echo ""
        read -p "Enter your Gemini API key: " API_KEY
        
        if [ -z "$API_KEY" ]; then
            echo -e "${RED}✗ No API key provided. Agent features will not work.${NC}"
        else
            export GEMINI_API_KEY="$API_KEY"
            # Ask if they want to save it
            read -p "Save API key for future sessions? (y/n): " SAVE_KEY
            if [ "$SAVE_KEY" = "y" ] || [ "$SAVE_KEY" = "Y" ]; then
                echo "$API_KEY" > "$KEY_FILE"
                chmod 600 "$KEY_FILE"
                echo -e "${GREEN}✓ API key saved to .gemini_api_key${NC}"
            fi
        fi
    fi
else
    echo -e "${GREEN}✓ Gemini API key found in environment${NC}"
fi

echo ""

# Verify binaries exist
TRACERS="syscall_tracer sched_tracer page_fault_tracer io_latency_tracer scraper_daemon"
for tracer in $TRACERS; do
    if [ ! -f "$BUILD_DIR/$tracer" ]; then
        echo -e "${RED}✗ Missing: $tracer${NC}"
        echo "Run: cd build && cmake .. && make"
        exit 1
    fi
done

# Check for gnome-terminal
if ! command -v gnome-terminal &> /dev/null; then
    echo -e "${RED}✗ gnome-terminal not found. Install with: sudo apt install gnome-terminal${NC}"
    exit 1
fi

# IMPORTANT: Do NOT run this script with sudo! Each tracer uses sudo internally.
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}ERROR: Do not run this script as root/sudo!${NC}"
    echo "Run without sudo: ./start_kernelsight.sh"
    echo "Each tracer will ask for sudo password when needed."
    exit 1
fi

# Setup passwordless sudo for tracers if not already configured
SUDOERS_FILE="/etc/sudoers.d/kernelsight"
if [ ! -f "$SUDOERS_FILE" ]; then
    echo -e "${YELLOW}Setting up passwordless sudo for tracers (one-time setup)...${NC}"
    sudo "$PROJECT_ROOT/scripts/setup_sudo.sh"
else
    echo -e "${GREEN}✓ Sudoers already configured${NC}"
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Initialize database
SEMANTIC_DAEMON="$PROJECT_ROOT/src/pipeline/semantic_ingestion_daemon.py"
python3 "$SEMANTIC_DAEMON" --db-path "$DB_PATH" --init-only
echo -e "${GREEN}✓ Database initialized${NC}"

cd "$BUILD_DIR"

echo ""

if [ "$LITE_MODE" = true ]; then
    # LITE MODE: Run tracers in background without terminals (low CPU)
    echo -e "${GREEN}🚀 Launching tracers in background (lite mode)...${NC}"
    
    # Start ingestion daemon in background
    echo "  Starting ingestion daemon..."
    cd "$PROJECT_ROOT"
    source "$VENV_DIR/bin/activate" 2>/dev/null || true
    python3 "$SEMANTIC_DAEMON" --db-path "$DB_PATH" \
        --watch-files "$LOG_DIR/syscall.log" "$LOG_DIR/scheduler.log" "$LOG_DIR/pagefault.log" "$LOG_DIR/io.log" "$LOG_DIR/scraper.log" \
        > "$LOG_DIR/ingestion.log" 2>&1 &
    echo $! > "$LOG_DIR/ingestion.pid"
    
    # Start tracers in background
    cd "$BUILD_DIR"
    echo "  Starting eBPF tracers..."
    sudo ./syscall_tracer > "$LOG_DIR/syscall.log" 2> "$LOG_DIR/syscall_err.log" &
    sudo ./sched_tracer > "$LOG_DIR/scheduler.log" 2> "$LOG_DIR/scheduler_err.log" &
    sudo ./page_fault_tracer > "$LOG_DIR/pagefault.log" 2> "$LOG_DIR/pagefault_err.log" &
    sudo ./io_latency_tracer > "$LOG_DIR/io.log" 2> "$LOG_DIR/io_err.log" &
    ./scraper_daemon > "$LOG_DIR/scraper.log" 2> "$LOG_DIR/scraper_err.log" &
    
    echo -e "${GREEN}✓ All tracers running in background${NC}"
    echo "  Logs: $LOG_DIR"
    
    sleep 2
else
    # STANDARD MODE: Run tracers in terminal windows
    echo -e "${GREEN}🚀 Launching components in separate terminal windows...${NC}"
    
    # Launch Ingestion Daemon
    echo "  [1] Semantic Ingestion Daemon"
    gnome-terminal --title="Ingestion Daemon" --geometry=120x30 -- bash -c "
        cd '$PROJECT_ROOT'
        source '$VENV_DIR/bin/activate' 2>/dev/null || true
        echo '=== Semantic Ingestion Daemon ==='
        python3 '$SEMANTIC_DAEMON' --db-path '$DB_PATH' \\
            --watch-files '$LOG_DIR/syscall.log' '$LOG_DIR/scheduler.log' '$LOG_DIR/pagefault.log' '$LOG_DIR/io.log' '$LOG_DIR/scraper.log' \\
            2>&1 | tee '$LOG_DIR/ingestion.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    sleep 1
    
    # Launch Syscall Tracer
    echo "  [2] Syscall Tracer"
    gnome-terminal --title="Syscall Tracer" --geometry=100x20 -- bash -c "
        cd '$BUILD_DIR'
        echo '=== Syscall Tracer ==='
        sudo stdbuf -oL ./syscall_tracer 2>'$LOG_DIR/syscall_err.log' | stdbuf -oL tee '$LOG_DIR/syscall.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    # Launch Scheduler Tracer
    echo "  [3] Scheduler Tracer"
    gnome-terminal --title="Scheduler Tracer" --geometry=100x20 -- bash -c "
        cd '$BUILD_DIR'
        echo '=== Scheduler Tracer ==='
        sudo stdbuf -oL ./sched_tracer 2>'$LOG_DIR/scheduler_err.log' | stdbuf -oL tee '$LOG_DIR/scheduler.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    # Launch Page Fault Tracer
    echo "  [4] Page Fault Tracer"
    gnome-terminal --title="Page Fault Tracer" --geometry=100x20 -- bash -c "
        cd '$BUILD_DIR'
        echo '=== Page Fault Tracer ==='
        sudo stdbuf -oL ./page_fault_tracer 2>'$LOG_DIR/pagefault_err.log' | stdbuf -oL tee '$LOG_DIR/pagefault.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    # Launch I/O Latency Tracer
    echo "  [5] I/O Latency Tracer"
    gnome-terminal --title="IO Latency Tracer" --geometry=100x20 -- bash -c "
        cd '$BUILD_DIR'
        echo '=== I/O Latency Tracer ==='
        sudo stdbuf -oL ./io_latency_tracer 2>'$LOG_DIR/io_err.log' | stdbuf -oL tee '$LOG_DIR/io.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    # Launch Scraper Daemon
    echo "  [6] Scraper Daemon"
    gnome-terminal --title="Scraper Daemon" --geometry=100x20 -- bash -c "
        cd '$BUILD_DIR'
        echo '=== Scraper Daemon ==='
        stdbuf -oL ./scraper_daemon 2>'$LOG_DIR/scraper_err.log' | stdbuf -oL tee '$LOG_DIR/scraper.log'
        echo ''
        read -p 'Press Enter to close...'
    " &
    
    sleep 2
fi

# Create autonomous loop script
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

logger.info('=== KernelSight AI Autonomous Loop ===')
logger.info(f'Database: {DB_PATH}')
logger.info(f'Check Interval: {INTERVAL}s')
logger.info('User approval required before executing actions')

agent = AutonomousAgent(DB_PATH, require_approval=True)
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

# Launch Agent(s)
if [ "$RUN_AGENT" = true ]; then
    if [ "$UNIFIED_MODE" = true ]; then
        # Unified mode: single terminal with both autonomous + interactive
        echo "  [7] Unified Agent (monitoring + chat in one)"
        gnome-terminal --title="Unified Agent" --geometry=140x40 -- bash -c "
            cd '$PROJECT_ROOT'
            source '$VENV_DIR/bin/activate' 2>/dev/null || true
            export GEMINI_API_KEY=\"\$GEMINI_API_KEY\"
            python3 unified_agent.py --db '$DB_PATH' --interval '$AGENT_INTERVAL' 2>&1
            echo ''
            read -p 'Press Enter to close...'
        " &
    else
        # Standard mode: separate terminals
        echo "  [7] Autonomous Loop (continuous - you can type y/N)"
        gnome-terminal --title="Autonomous Agent Loop" --geometry=140x40 -- bash -c "
            cd '$PROJECT_ROOT'
            source '$VENV_DIR/bin/activate' 2>/dev/null || true
            export PROJECT_ROOT='$PROJECT_ROOT'
            export DB_PATH='$DB_PATH'
            export AGENT_INTERVAL='$AGENT_INTERVAL'
            python3 '$LOG_DIR/run_autonomous_loop.py' 2>&1
            echo ''
            read -p 'Press Enter to close...'
        " &
        
        # Window 8: Interactive Agent (for manual queries with Gemini)
        echo "  [8] Interactive Agent (Gemini-powered chat)"
        gnome-terminal --title="Interactive Agent" --geometry=140x40 -- bash -c "
            cd '$PROJECT_ROOT'
            source '$VENV_DIR/bin/activate' 2>/dev/null || true
            echo '=== KernelSight AI Interactive Agent ==='
            echo 'Database: $DB_PATH'
            echo ''
            echo 'Ask questions about system health, issues, or request analysis.'
            echo ''
            python3 interactive_agent.py --db '$DB_PATH' 2>&1
            echo ''
            read -p 'Press Enter to close...'
        " &
    fi
fi

echo ""
echo -e "${GREEN}=========================================="
echo "✓ KernelSight AI System Started!"
echo -e "==========================================${NC}"
echo ""
if [ "$LITE_MODE" = true ]; then
    echo "Mode: LITE (low CPU)"
    echo "  - Tracers running in background (no terminals)"
    echo "  - Unified Agent terminal open"
    echo ""
    echo "Logs: $LOG_DIR"
else
    echo "Components running:"
    if [ "$UNIFIED_MODE" = true ]; then
        echo "  [1-6] Telemetry collectors (terminals)"
        echo "  [7]   Unified Agent (monitoring + chat)"
    else
        echo "  [1-6] Telemetry collectors (terminals)"
        echo "  [7]   Autonomous Loop (continuous monitoring)"
        echo "  [8]   Interactive Agent (chat with Gemini)"
    fi
fi
echo ""
echo "To stop all: ./stop_kernelsight.sh"

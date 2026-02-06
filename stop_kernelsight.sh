#!/bin/bash
# KernelSight AI - Stop Script
# Cleanly stops all KernelSight terminal windows

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Stopping KernelSight AI...${NC}"

# Kill gnome-terminal windows with specific titles
WINDOWS=("Ingestion Daemon" "Syscall Tracer" "Scheduler Tracer" "Page Fault Tracer" "IO Latency Tracer" "Scraper Daemon" "Autonomous Agent Loop" "Interactive Agent")

killed=0
for title in "${WINDOWS[@]}"; do
    # Find window by title and kill
    pid=$(xdotool search --name "$title" 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        wmctrl -c "$title" 2>/dev/null || true
        ((killed++))
    fi
done

# Also kill any sudo tracers that might be running
echo -e "${YELLOW}Stopping eBPF tracers...${NC}"
sudo pkill -f "syscall_tracer" 2>/dev/null || true
sudo pkill -f "sched_tracer" 2>/dev/null || true
sudo pkill -f "page_fault_tracer" 2>/dev/null || true
sudo pkill -f "io_latency_tracer" 2>/dev/null || true
pkill -f "scraper_daemon" 2>/dev/null || true
pkill -f "semantic_ingestion_daemon" 2>/dev/null || true
pkill -f "autonomous_loop" 2>/dev/null || true
pkill -f "interactive_agent" 2>/dev/null || true

echo ""
echo -e "${GREEN}✓ KernelSight AI stopped${NC}"
echo "  Closed $killed terminal windows"
echo "  Killed eBPF tracers and daemons"

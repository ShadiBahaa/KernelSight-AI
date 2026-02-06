#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Agent Activity Monitor

Watch the autonomous agent in real-time:
- Current analysis phase
- Signals being observed
- Actions being taken
- Command execution results
"""

import sqlite3
import time
import sys
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "kernelsight.db"
AGENT_LOG = Path(__file__).parent / "logs" / "production" / "agent.log"


def clear_screen():
    """Clear terminal screen."""
    print("\033[2J\033[H", end="")


def get_recent_agent_activity(conn):
    """Get recent agent decisions and actions."""
    cursor = conn.cursor()
    
    # Get recent decision logs from agent_actions table (if it exists)
    try:
        actions = cursor.execute("""
            SELECT timestamp, action_type, status, result_summary
            FROM agent_actions
            ORDER BY timestamp DESC
            LIMIT 10
        """).fetchall()
    except:
        actions = []
    
    return actions


def get_agent_log_tail(lines=20):
    """Get last N lines from agent log."""
    if not AGENT_LOG.exists():
        return ["Agent log not found - agent may not be running"]
    
    try:
        with open(AGENT_LOG, 'r') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if all_lines else ["No agent activity yet"]
    except:
        return ["Could not read agent log"]


def parse_log_line(line):
    """Parse and colorize log line."""
    line = line.strip()
    
    # Colorize by log level
    if 'ERROR' in line:
        return f"\033[91m{line}\033[0m"  # Red
    elif 'WARNING' in line:
        return f"\033[93m{line}\033[0m"  # Yellow
    elif 'OBSERVE' in line or 'EXPLAIN' in line or 'SIMULATE' in line:
        return f"\033[96m{line}\033[0m"  # Cyan
    elif 'DECIDE' in line:
        return f"\033[95m{line}\033[0m"  # Magenta
    elif 'EXECUTE' in line:
        return f"\033[92m{line}\033[0m"  # Green
    elif 'VERIFY' in line:
        return f"\033[94m{line}\033[0m"  # Blue
    elif 'Iteration' in line:
        return f"\033[1m{line}\033[0m"  # Bold
    
    return line


def display_monitor():
    """Display real-time agent activity."""
    clear_screen()
    
    print("=" * 80)
    print("KernelSight AI - Agent Activity Monitor".center(80))
    print("=" * 80)
    print()
    
    # Check if agent is running
    if not AGENT_LOG.exists():
        print("⚠️  Agent log not found")
        print()
        print("The autonomous agent may not be running.")
        print("Start it with: sudo python3 run_kernelsight.py")
        print()
        print("=" * 80)
        return
    
    # Get file modification time
    try:
        mtime = os.path.getmtime(AGENT_LOG)
        last_update = datetime.fromtimestamp(mtime)
        age_seconds = time.time() - mtime
        
        if age_seconds > 120:
            status = f"⚠️  Last activity: {int(age_seconds)}s ago (agent may be idle)"
        elif age_seconds > 60:
            status = f"🟡 Last activity: {int(age_seconds)}s ago"
        else:
            status = f"🟢 Active (updated {int(age_seconds)}s ago)"
        
        print(f"Status: {status}")
        print(f"Log: {AGENT_LOG}")
        print()
    except:
        print("Status: Unknown")
        print()
    
    # Show recent log activity
    print("📋 RECENT AGENT ACTIVITY")
    print("-" * 80)
    
    log_lines = get_agent_log_tail(25)
    
    for line in log_lines:
        colored_line = parse_log_line(line)
        # Truncate long lines
        if len(line) > 200:
            colored_line = colored_line[:197] + "..."
        print(colored_line)
    
    print()
    print("=" * 80)
    print("🔵 OBSERVE  🟣 DECIDE  🟢 EXECUTE  🔴 ERROR  🟡 WARNING")
    print()
    print(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Press Ctrl+C to exit")


def main():
    """Main monitoring loop."""
    try:
        print("Starting agent monitor... (updates every 2 seconds)")
        print("Make sure the system is running: sudo python3 run_kernelsight.py")
        print()
        time.sleep(2)
        
        while True:
            display_monitor()
            time.sleep(2)
    
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

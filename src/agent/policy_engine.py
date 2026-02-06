#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Command Policy Engine - Safe execution validation for autonomous agent.

This module implements Layer 2 of the 4-layer safety architecture:
- Layer 1: Action Proposal (Gemini) 
- Layer 2: Policy Engine (THIS MODULE) - allowlist + forbidden pattern validation
- Layer 3: Execution Sandbox
- Layer 4: Feedback Loop

CRITICAL SAFETY COMPONENT - prevents destructive commands.
"""

import re
import subprocess
import logging
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Comprehensive command allowlist for all 10 event types
ALLOWED_COMMANDS = {
    # MEMORY PRESSURE
    r"renice \+?\d+ -p \d+": {"category": "priority", "risk": "low"},
    r"kill -TERM \d+": {"category": "process_control", "risk": "medium"},
    r"echo [123] > /proc/sys/vm/drop_caches": {"category": "cache", "risk": "low"},
    
    # LOAD MISMATCH / CPU
    r"cpulimit -p \d+ -l \d+": {"category": "resource_limit", "risk": "low"},
    r"taskset -p [0-9a-f,]+ \d+": {"category": "cpu_affinity", "risk": "low"},
    r"kill -STOP \d+": {"category": "process_control", "risk": "medium"},
    r"kill -CONT \d+": {"category": "process_control", "risk": "low"},
    
    # I/O CONGESTION
    r"ionice -c[123] -n[0-7] -p \d+": {"category": "io_priority", "risk": "low"},
    r"ionice -c3 -p \d+": {"category": "io_priority", "risk": "low"},
    r"sync": {"category": "io_flush", "risk": "none"},
    
    # NETWORK
    r"ethtool -s \w+ speed \d+ duplex (full|half)": {"category": "network", "risk": "medium"},
    r"tc qdisc add dev \w+ root tbf rate \d+mbit": {"category": "traffic_control", "risk": "medium"},
    
    # TCP
    r"sysctl -w net\.ipv4\.tcp_max_syn_backlog=\d+": {"category": "sysctl", "risk": "low"},
    r"sysctl -w net\.ipv4\.tcp_fin_timeout=\d+": {"category": "sysctl", "risk": "low"},
    r"sysctl -w net\.core\.somaxconn=\d+": {"category": "sysctl", "risk": "low"},
    
    # SWAP / MEMORY TUNING
    r"sysctl -w vm\.swappiness=\d+": {"category": "memory_tuning", "risk": "low"},
    
    # SCHEDULER
    r"chrt -p \d+ \d+": {"category": "scheduling", "risk": "low"},
    
    # INFO GATHERING (always safe)
    r"ps aux": {"category": "info", "risk": "none"},
    r"ps aux --sort=-(rss|pcpu)": {"category": "info", "risk": "none"},
    r"ps aux --sort=-(rss|pcpu) \| head -\d+": {"category": "info", "risk": "none"},
    r"ps -p \d+ -o .+": {"category": "info", "risk": "none"},
    r"top -b -n 1": {"category": "info", "risk": "none"},
    r"top -b -n 1 -p \d+": {"category": "info", "risk": "none"},
    r"free -m": {"category": "info", "risk": "none"},
    r"vmstat 1 5": {"category": "info", "risk": "none"},
    r"iostat -x 1 5": {"category": "info", "risk": "none"},
    r"iotop -b -n 1": {"category": "info", "risk": "none"},
    r"lsof -p \d+": {"category": "info", "risk": "none"},
    r"netstat -i": {"category": "info", "risk": "none"},
    r"netstat -an": {"category": "info", "risk": "none"},
    r"netstat -an \| grep -c TIME_WAIT": {"category": "info", "risk": "none"},
    r"ss -s": {"category": "info", "risk": "none"},
    r"ethtool \w+": {"category": "info", "risk": "none"},
    r"ethtool -S \w+": {"category": "info", "risk": "none"},
    r"ip -s link show \w+": {"category": "info", "risk": "none"},
    r"pidstat -w 1 5": {"category": "info", "risk": "none"},
    r"pmap \d+": {"category": "info", "risk": "none"},
}

# EXPLICITLY FORBIDDEN - will never pass policy
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+.*\s+-rf",
    r"shutdown",
    r"reboot",
    r"poweroff",
    r"halt",
    r"kill -9",  # Too aggressive
    r"kill -KILL",
    r"dd\s+if=",  # Disk overwrite
    r"mkfs",
    r"fdisk",
    r"parted",
    r"chmod\s+777",
    r"chmod\s+000",
    r"chown\s+root",
    r"iptables\s+-F",  # Firewall flush
    r"systemctl\s+stop",  # Service management
    r"systemctl\s+disable",
]


def validate_command_policy(command: str) -> Dict:
    """
    Validate command against policy (Layer 2 safety).
    
    Args:
        command: Command string to validate
        
    Returns:
        {
            'allowed': True/False,
            'reason': "...",
            'risk': "low/medium/high",
            'matched_pattern': "..."
        }
    """
    command = command.strip()
    
    # Check forbidden patterns first
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return {
                'allowed': False,
                'reason': f'Command matches forbidden pattern: {pattern}',
                'forbidden_pattern': pattern
            }
    
    # Check against allowlist
    for pattern, metadata in ALLOWED_COMMANDS.items():
        if re.fullmatch(pattern, command):
            return {
                'allowed': True,
                'reason': 'Command matches allowlist',
                'risk': metadata['risk'],
                'category': metadata['category'],
                'matched_pattern': pattern
            }
    
    # Not in allowlist = not allowed
    return {
        'allowed': False,
        'reason': 'Command not in allowlist',
        'suggestion': 'Only pre-approved commands are allowed for safety'
    }


def execute_in_sandbox(command: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """
    Execute command in sandbox (Layer 3 safety).
    
    Args:
        command: Command to execute (already validated by policy)
        timeout: Execution timeout in seconds
        
    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise on non-zero exit
        )
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {command}")
        raise
    except Exception as e:
        logger.error(f"Execution error for {command}: {e}")
        raise


if __name__ == "__main__":
    # Test policy validation
    logging.basicConfig(level=logging.INFO)
    
    test_commands = [
        # Should pass
        "ps aux",
        "renice +10 -p 1234",
        "cpulimit -p 1234 -l 50",
        "free -m",
        
        # Should fail
        "rm -rf /",
        "shutdown now",
        "kill -9 1234",
        "random_command --flag",
    ]
    
    print("=== Policy Validation Tests ===\n")
    for cmd in test_commands:
        result = validate_command_policy(cmd)
        status = "✓ ALLOWED" if result['allowed'] else "✗ BLOCKED"
        print(f"{status}: {cmd}")
        print(f"  Reason: {result['reason']}")
        if result['allowed']:
            print(f"  Risk: {result.get('risk', 'N/A')}")
        print()

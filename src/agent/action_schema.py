#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Action Schema - Structured action types for hybrid autonomous execution.

This module defines the action catalog where:
- Gemini proposes ACTION TYPES (not raw commands)
- System maps action_type → concrete command template
- Deterministic safety through structured execution

This is the GOLD STANDARD for autonomous systems.
"""

from typing import Dict, List, Optional, Any
from enum import Enum


class ActionType(Enum):
    """Structured action types that Gemini can propose."""
    
    # Process Priority Management
    LOWER_PROCESS_PRIORITY = "lower_process_priority"
    THROTTLE_CPU = "throttle_cpu"
    SET_CPU_AFFINITY = "set_cpu_affinity"
    
    # Process Control
    PAUSE_PROCESS = "pause_process"
    RESUME_PROCESS = "resume_process"
    TERMINATE_PROCESS = "terminate_process"
    
    # I/O Management
    LOWER_IO_PRIORITY = "lower_io_priority"
    FLUSH_BUFFERS = "flush_buffers"
    
    # Memory Management  
    REDUCE_SWAPPINESS = "reduce_swappiness"
    CLEAR_PAGE_CACHE = "clear_page_cache"
    
    # Network Tuning
    INCREASE_TCP_BACKLOG = "increase_tcp_backlog"
    REDUCE_FIN_TIMEOUT = "reduce_fin_timeout"
    FORCE_NETWORK_SPEED = "force_network_speed"
    
    # Information Gathering
    LIST_TOP_MEMORY = "list_top_memory"
    LIST_TOP_CPU = "list_top_cpu"
    CHECK_IO_ACTIVITY = "check_io_activity"
    CHECK_NETWORK_STATS = "check_network_stats"
    CHECK_TCP_STATS = "check_tcp_stats"
    MONITOR_SWAP = "monitor_swap"


# Action catalog: Maps action_type → command template + metadata
ACTION_CATALOG = {
    # ========================================
    # PROCESS PRIORITY
    # ========================================
    ActionType.LOWER_PROCESS_PRIORITY: {
        "command_template": "renice +{priority} -p {pid}",
        "required_params": ["pid"],
        "optional_params": {"priority": 10},
        "risk": "low",
        "description": "Lower process priority to reduce resource usage",
        "rollback_template": "renice -{priority} -p {pid}",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0,
            "priority": lambda p: isinstance(p, int) and 1 <= p <= 20
        },
        # Day 11: Operational safety metadata
        "reversible": True,
        "blast_radius": "single_process",
        "prerequisites": ["process_exists"],
        "side_effects": ["reduced_responsiveness"],
        "verification": {
            "check_command": "ps -p {pid} -o nice",
            "success_indicator": "increased_nice_value"
        }
    },
    
    ActionType.THROTTLE_CPU: {
        "command_template": "cpulimit -p {pid} -l {limit}",
        "required_params": ["pid", "limit"],
        "optional_params": {},
        "risk": "low",
        "description": "Limit CPU usage to percentage",
        "rollback": "Kill cpulimit process",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0,
            "limit": lambda l: isinstance(l, int) and 1 <= l <= 100
        }
    },
    
    ActionType.SET_CPU_AFFINITY: {
        "command_template": "taskset -p {cpus} {pid}",
        "required_params": ["pid", "cpus"],
        "optional_params": {},
        "risk": "low",
        "description": "Set CPU affinity for process",
        "rollback": "Reset to all CPUs",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0,
            "cpus": lambda c: isinstance(c, str) and all(x.isdigit() or x in ',-' for x in c)
        }
    },
    
    # ========================================
    # PROCESS CONTROL
    # ========================================
    ActionType.PAUSE_PROCESS: {
        "command_template": "kill -STOP {pid}",
        "required_params": ["pid"],
        "optional_params": {},
        "risk": "medium",
        "description": "Pause process execution",
        "rollback_template": "kill -CONT {pid}",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0
        }
    },
    
    ActionType.RESUME_PROCESS: {
        "command_template": "kill -CONT {pid}",
        "required_params": ["pid"],
        "optional_params": {},
        "risk": "low",
        "description": "Resume paused process",
        "rollback": "N/A",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0
        }
    },
    
    ActionType.TERMINATE_PROCESS: {
        "command_template": "kill -TERM {pid}",
        "required_params": ["pid"],
        "optional_params": {},
        "risk": "medium",
        "description": "Gracefully terminate process",
        "rollback": "Restart service if critical",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0
        }
    },
    
    # ========================================
    # I/O MANAGEMENT
    # ========================================
    ActionType.LOWER_IO_PRIORITY: {
        "command_template": "ionice -c{io_class} -n{priority} -p {pid}",
        "required_params": ["pid"],
        "optional_params": {"io_class": 2, "priority": 7},
        "risk": "low",
        "description": "Lower I/O scheduling priority",
        "rollback_template": "ionice -c2 -n0 -p {pid}",
        "validation": {
            "pid": lambda p: isinstance(p, int) and p > 0,
            "io_class": lambda c: c in [1, 2, 3],
            "priority": lambda p: 0 <= p <= 7
        }
    },
    
    ActionType.FLUSH_BUFFERS: {
        "command_template": "sync",
        "required_params": [],
        "optional_params": {},
        "risk": "none",
        "description": "Flush filesystem buffers",
        "rollback": "N/A",
        "validation": {}
    },
    
    # ========================================
    # MEMORY MANAGEMENT
    # ========================================
    ActionType.REDUCE_SWAPPINESS: {
        "command_template": "sysctl -w vm.swappiness={value}",
        "required_params": [],
        "optional_params": {"value": 10},
        "risk": "low",
        "description": "Reduce swap aggressiveness",
        "rollback_template": "sysctl -w vm.swappiness=60",
        "validation": {
            "value": lambda v: 0 <= v <= 100
        }
    },
    
    ActionType.CLEAR_PAGE_CACHE: {
        "command_template": "echo {level} > /proc/sys/vm/drop_caches",
        "required_params": [],
        "optional_params": {"level": 1},
        "risk": "low",
        "description": "Clear page cache to free memory",
        "rollback": "N/A (caches rebuild automatically)",
        "validation": {
            "level": lambda l: l in [1, 2, 3]
        }
    },
    
    # ========================================
    # NETWORK / TCP TUNING
    # ========================================
    ActionType.INCREASE_TCP_BACKLOG: {
        "command_template": "sysctl -w net.ipv4.tcp_max_syn_backlog={value}",
        "required_params": [],
        "optional_params": {"value": 4096},
        "risk": "low",
        "description": "Increase TCP SYN backlog",
        "rollback_template": "sysctl -w net.ipv4.tcp_max_syn_backlog=1024",
        "validation": {
            "value": lambda v: 128 <= v <= 65536
        }
    },
    
    ActionType.REDUCE_FIN_TIMEOUT: {
        "command_template": "sysctl -w net.ipv4.tcp_fin_timeout={value}",
        "required_params": [],
        "optional_params": {"value": 30},
        "risk": "low",
        "description": "Reduce TCP FIN timeout",
        "rollback_template": "sysctl -w net.ipv4.tcp_fin_timeout=60",
        "validation": {
            "value": lambda v: 10 <= v <= 120
        }
    },
    
    # ========================================
    # INFORMATION GATHERING (always safe)
    # ========================================
    ActionType.LIST_TOP_MEMORY: {
        "command_template": "ps aux --sort=-rss | head -{count}",
        "required_params": [],
        "optional_params": {"count": 10},
        "risk": "none",
        "description": "List top memory consumers",
        "rollback": "N/A",
        "validation": {
            "count": lambda c: 1 <= c <= 50
        }
    },
    
    ActionType.LIST_TOP_CPU: {
        "command_template": "ps aux --sort=-pcpu | head -{count}",
        "required_params": [],
        "optional_params": {"count": 10},
        "risk": "none",
        "description": "List top CPU consumers",
        "rollback": "N/A",
        "validation": {
            "count": lambda c: 1 <= c <= 50
        }
    },
    
    ActionType.CHECK_IO_ACTIVITY: {
        "command_template": "iotop -b -n 1",
        "required_params": [],
        "optional_params": {},
        "risk": "none",
        "description": "Check I/O activity",
        "rollback": "N/A",
        "validation": {}
    },
    
    ActionType.CHECK_NETWORK_STATS: {
        "command_template": "netstat -i",
        "required_params": [],
        "optional_params": {},
        "risk": "none",
        "description": "Check network interface statistics",
        "rollback": "N/A",
        "validation": {}
    },
    
    ActionType.CHECK_TCP_STATS: {
        "command_template": "ss -s",
        "required_params": [],
        "optional_params": {},
        "risk": "none",
        "description": "Check TCP socket statistics",
        "rollback": "N/A",
        "validation": {}
    },
    
    ActionType.MONITOR_SWAP: {
        "command_template": "vmstat 1 5",
        "required_params": [],
        "optional_params": {},
        "risk": "none",
        "description": "Monitor swap activity",
        "rollback": "N/A",
        "validation": {}
    },
}


def build_command(action_type: ActionType, params: Dict[str, Any]) -> Dict:
    """
    Build concrete command from action type + parameters.
    
    This is the CORE of the hybrid model - Gemini never sees raw commands.
    
    Args:
        action_type: Structured action type
        params: Parameters for the action
        
    Returns:
        {
            'command': "renice +10 -p 1234",
            'risk': "low",
            'description': "...",
            'rollback': "...",
            'valid': True/False,
            'errors': [...]
        }
    """
    if action_type not in ACTION_CATALOG:
        return {
            'valid': False,
            'errors': [f'Unknown action type: {action_type}']
        }
    
    action_spec = ACTION_CATALOG[action_type]
    
    # Merge with defaults
    final_params = {**action_spec['optional_params'], **params}
    
    # Validate required params
    errors = []
    for req in action_spec['required_params']:
        if req not in final_params:
            errors.append(f'Missing required parameter: {req}')
    
    # Validate parameter values
    for key, value in final_params.items():
        if key in action_spec['validation']:
            validator = action_spec['validation'][key]
            if not validator(value):
                errors.append(f'Invalid value for {key}: {value}')
    
    if errors:
        return {
            'valid': False,
            'errors': errors
        }
    
    # Build command from template
    command = action_spec['command_template'].format(**final_params)
    
    # Build rollback if template exists
    rollback = action_spec.get('rollback_template')
    if rollback:
        rollback = rollback.format(**final_params)
    else:
        rollback = action_spec.get('rollback', 'N/A')
    
    return {
        'valid': True,
        'command': command,
        'risk': action_spec['risk'],
        'description': action_spec['description'],
        'rollback': rollback,
        'action_type': action_type.value,
        'parameters': final_params
    }


if __name__ == "__main__":
    # Test action building
    print("=== Hybrid Action Model Tests ===\n")
    
    # Test 1: Lower process priority
    result = build_command(
        ActionType.LOWER_PROCESS_PRIORITY,
        {"pid": 1234, "priority": 10}
    )
    print(f"✓ LOWER_PROCESS_PRIORITY: {result['command']}")
    print(f"  Risk: {result['risk']}, Rollback: {result['rollback']}\n")
    
    # Test 2: Throttle CPU
    result = build_command(
        ActionType.THROTTLE_CPU,
        {"pid": 5678, "limit": 50}
    )
    print(f"✓ THROTTLE_CPU: {result['command']}")
    print(f"  Risk: {result['risk']}\n")
    
    # Test 3: Info gathering (no params needed)
    result = build_command(
        ActionType.LIST_TOP_MEMORY,
        {}
    )
    print(f"✓ LIST_TOP_MEMORY: {result['command']}")
    print(f"  Risk: {result['risk']}\n")
    
    # Test 4: Validation error
    result = build_command(
        ActionType.LOWER_PROCESS_PRIORITY,
        {"pid": -1}  # Invalid
    )
    print(f"✗ Invalid PID: {result.get('errors')}\n")

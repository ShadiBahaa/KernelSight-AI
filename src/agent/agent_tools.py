#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Agent Tools - Function implementations for Gemini 3 function calling.

This module provides the 5 tools that enable Gemini 3 to query system state,
analyze trends, simulate scenarios, get recommendations, and execute commands.
"""

import sys
import os
import logging
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analysis.trend_analyzer import TrendAnalyzer
from analysis.baseline_analyzer import BaselineAnalyzer
from agent.counterfactual_simulator import CounterfactualSimulator

logger = logging.getLogger(__name__)


class AgentTools:
    """Collection of tools for Gemini 3 agent."""
    
    def __init__(self, db_path: str):
        """
        Initialize agent tools.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Initialize analyzers
        self.trend_analyzer = TrendAnalyzer(db_path)
        self.baseline_analyzer = BaselineAnalyzer(db_path)
        self.simulator = CounterfactualSimulator()
    
    def query_signals(self,
                     signal_types: Optional[List[str]] = None,
                     severity_min: str = "low",
                     limit: int = 20,
                     lookback_minutes: int = 30) -> Dict:
        """
        Query recent semantic signals to understand current system state.
        
        Args:
            signal_types: Filter by signal types (empty = all)
            severity_min: Minimum severity ('low', 'medium', 'high', 'critical')
            limit: Maximum signals to return
            lookback_minutes: How far back to look
            
        Returns:
            {
                'signal_count': 5,
                'signals': [...],
                'summary': "..."
            }
        """
        severity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        min_level = severity_order.get(severity_min, 0)
        
        # Build query
        since_ts = int((datetime.now() - timedelta(minutes=lookback_minutes)).timestamp() * 1_000_000_000)
        
        query = """
            SELECT 
                timestamp, signal_type, severity, pressure_score,
                summary, semantic_label
            FROM signal_metadata
            WHERE timestamp >= ?
        """
        params = [since_ts]
        
        if signal_types:
            placeholders = ','.join(['?'] * len(signal_types))
            query += f" AND signal_type IN ({placeholders})"
            params.extend(signal_types)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Filter by severity
        signals = []
        for row in rows:
            row_severity = row['severity'] or 'low'
            if severity_order.get(row_severity, 0) >= min_level:
                signals.append({
                    'timestamp': row['timestamp'],
                    'signal_type': row['signal_type'],
                    'severity': row_severity,
                    'pressure_score': row['pressure_score'],
                    'summary': row['summary'],
                    'label': row['semantic_label']
                })
        
        # Generate summary
        if signals:
            types_count = {}
            for s in signals:
                types_count[s['signal_type']] = types_count.get(s['signal_type'], 0) + 1
            
            summary_parts = [f"{count} {stype}" for stype, count in types_count.items()]
            summary = f"Found {len(signals)} signals: " + ", ".join(summary_parts)
        else:
            summary = "No signals found matching criteria"
        
        return {
            'signal_count': len(signals),
            'signals': signals[:limit],
            'summary': summary,
            'lookback_minutes': lookback_minutes
        }
    
    def summarize_trends(self,
                        signal_types: List[str],
                        lookback_minutes: int = 30) -> Dict:
        """
        Analyze trends in system metrics to detect increasing/decreasing pressure.
        
        Args:
            signal_types: Which signal types to analyze
            lookback_minutes: Window for trend calculation
            
        Returns:
            {
                'trends': {
                    'memory_pressure': {...},
                    'load_mismatch': {...}
                },
                'summary': "..."
            }
        """
        trends = {}
        
        for signal_type in signal_types:
            trend = self.trend_analyzer.calculate_trend_slope(
                signal_type, lookback_minutes
            )
            if trend:
                trends[signal_type] = trend
        
        # Generate summary
        if trends:
            summary_parts = []
            for sig_type, trend in trends.items():
                direction = trend['trend_direction']
                slope = trend['slope']
                summary_parts.append(
                    f"{sig_type}: {direction} ({slope:+.4f}/min)"
                )
            summary = "; ".join(summary_parts)
        else:
            summary = "No trend data available for specified signal types"
        
        return {
            'trends': trends,
            'summary': summary
        }
    
    def simulate_scenario(self,
                         signal_type: str,
                         duration_minutes: int = 30,
                         custom_slope: Optional[float] = None) -> Dict:
        """
        Simulate future system state if current trend continues.
        
        Args:
            signal_type: Which metric to simulate
            duration_minutes: How far into future to project
            custom_slope: Override trend slope (optional)
            
        Returns:
            Simulation results from CounterfactualSimulator
        """
        # Get current trend
        trend = self.trend_analyzer.calculate_trend_slope(signal_type, lookback_minutes=30)
        
        if not trend and custom_slope is None:
            return {
                'error': f'No trend data for {signal_type} and no custom_slope provided',
                'signal_type': signal_type
            }
        
        current_value = trend['current_value'] if trend else 0.5
        slope = custom_slope if custom_slope is not None else (trend['slope'] if trend else 0)
        
        # Get baselines for comparison
        baselines = self.baseline_analyzer.load_baselines(max_age_hours=48)
        
        # Run simulation
        result = self.simulator.simulate_pressure(
            signal_type=signal_type,
            current_value=current_value,
            trend_slope=slope,
            duration_minutes=duration_minutes,
            baselines=baselines
        )
        
        return result
    
    def propose_action(self,
                      failure_mode: str,
                      urgency: str,
                      affected_entity: Optional[str] = None) -> Dict:
        """
        Propose corrective actions for a specific failure mode.
        
        Args:
            failure_mode: Type of failure (e.g., 'oom_risk', 'io_congestion')
            urgency: How urgent ('low', 'medium', 'high', 'critical')
            affected_entity: Process, device, or interface (optional)
            
        Returns:
            Action recommendations
        """
        # Comprehensive action catalog for all failure modes
        action_catalog = {
            # ========================================
            # MEMORY PRESSURE - OOM risk, memory leaks
            # ========================================
            'oom_risk': {
                'actions': [
                    {
                        'command': 'ps aux --sort=-rss | head -10',
                        'description': 'Identify top memory consumers',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'renice +10 -p {pid}',
                        'description': 'Lower priority of memory-hungry process',
                        'risk': 'low',
                        'rollback': 'renice -10 -p {pid}'
                    },
                    {
                        'command': 'kill -TERM {pid}',
                        'description': 'Gracefully terminate process',
                        'risk': 'medium',
                        'rollback': 'Restart service if critical'
                    }
                ],
                'diagnostics': ['ps aux --sort=-rss | head -20', 'free -m', 'vmstat 1 5']
            },
            'memory_leak': {
                'actions': [
                    {
                        'command': 'kill -TERM {pid}',
                        'description': 'Terminate leaking process',
                        'risk': 'medium',
                        'rollback': 'Restart service'
                    }
                ],
                'diagnostics': ['ps -p {pid} -o pid,vsz,rss,comm', 'pmap {pid}']
            },
            
            # ========================================
            # LOAD MISMATCH - CPU saturation
            # ========================================
            'cpu_saturation': {
                'actions': [
                    {
                        'command': 'ps aux --sort=-pcpu | head -10',
                        'description': 'Identify CPU hogs',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'cpulimit -p {pid} -l 50',
                        'description': 'Limit CPU usage to 50%',
                        'risk': 'low',
                        'rollback': 'Kill cpulimit process'
                    },
                    {
                        'command': 'renice +10 -p {pid}',
                        'description': 'Lower CPU priority',
                        'risk': 'low',
                        'rollback': 'renice -10 -p {pid}'
                    }
                ],
                'diagnostics': ['top -b -n 1', 'ps aux --sort=-pcpu | head -20']
            },
            'runaway_process': {
                'actions': [
                    {
                        'command': 'kill -STOP {pid}',
                        'description': 'Pause runaway process',
                        'risk': 'medium',
                        'rollback': 'kill -CONT {pid}'
                    },
                    {
                        'command': 'kill -TERM {pid}',
                        'description': 'Terminate runaway process',
                        'risk': 'medium',
                        'rollback': 'Restart service'
                    }
                ],
                'diagnostics': ['ps -p {pid} -o pid,pcpu,cputime,comm', 'top -b -n 1 -p {pid}']
            },
            
            # ========================================
            # I/O CONGESTION - Disk bottlenecks
            # ========================================
            'io_congestion': {
                'actions': [
                    {
                        'command': 'iotop -b -n 1',
                        'description': 'Identify I/O heavy processes',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'ionice -c2 -n7 -p {pid}',
                        'description': 'Lower I/O priority to idle class',
                        'risk': 'low',
                        'rollback': 'ionice -c2 -n0 -p {pid}'
                    },
                    {
                        'command': 'sync',
                        'description': 'Flush filesystem buffers',
                        'risk': 'none',
                        'rollback': 'N/A'
                    }
                ],
                'diagnostics': ['iotop -b -n 1', 'lsof -p {pid}', 'iostat -x 1 5']
            },
            'disk_thrashing': {
                'actions': [
                    {
                        'command': 'ionice -c3 -p {pid}',
                        'description': 'Set to idle I/O class',
                        'risk': 'low',
                        'rollback': 'ionice -c2 -n4 -p {pid}'
                    }
                ],
                'diagnostics': ['iostat -x 1 5', 'lsof -p {pid}']
            },
            
            # ========================================
            # NETWORK DEGRADATION - Packet loss, errors
            # ========================================
            'network_degradation': {
                'actions': [
                    {
                        'command': 'netstat -i',
                        'description': 'Check interface statistics',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'ethtool -s {interface} speed 1000 duplex full',
                        'description': 'Force gigabit full-duplex',
                        'risk': 'medium',
                        'rollback': 'ethtool -s {interface} autoneg on'
                    }
                ],
                'diagnostics': ['netstat -i', 'ethtool {interface}', 'ip -s link show {interface}']
            },
            'packet_loss': {
                'actions': [
                    {
                        'command': 'ethtool -S {interface}',
                        'description': 'Check detailed interface stats',
                        'risk': 'none',
                        'rollback': 'N/A'
                    }
                ],
                'diagnostics': ['ethtool -S {interface}', 'netstat -i']
            },
            
            # ========================================
            # TCP EXHAUSTION - Connection limits
            # ========================================
            'tcp_exhaustion': {
                'actions': [
                    {
                        'command': 'ss -s',
                        'description': 'Show socket statistics',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'sysctl -w net.ipv4.tcp_max_syn_backlog=4096',
                        'description': 'Increase SYN backlog',
                        'risk': 'low',
                        'rollback': 'sysctl -w net.ipv4.tcp_max_syn_backlog=1024'
                    },
                    {
                        'command': 'sysctl -w net.ipv4.tcp_fin_timeout=30',
                        'description': 'Reduce FIN timeout',
                        'risk': 'low',
                        'rollback': 'sysctl -w net.ipv4.tcp_fin_timeout=60'
                    }
                ],
                'diagnostics': ['ss -s', 'netstat -an | grep -c TIME_WAIT', 'sysctl net.ipv4.tcp_fin_timeout']
            },
            'connection_limit': {
                'actions': [
                    {
                        'command': 'sysctl -w net.core.somaxconn=2048',
                        'description': 'Increase listen backlog',
                        'risk': 'low',
                        'rollback': 'sysctl -w net.core.somaxconn=128'
                    }
                ],
                'diagnostics': ['ss -s', 'sysctl net.core.somaxconn']
            },
            
            # ========================================
            # SWAP THRASHING - Excessive swapping
            # ========================================
            'swap_thrashing': {
                'actions': [
                    {
                        'command': 'vmstat 1 5',
                        'description': 'Monitor swap activity',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'sysctl -w vm.swappiness=10',
                        'description': 'Reduce swap aggressiveness',
                        'risk': 'low',
                        'rollback': 'sysctl -w vm.swappiness=60'
                    },
                    {
                        'command': 'echo 1 > /proc/sys/vm/drop_caches',
                        'description': 'Clear page cache to free memory',
                        'risk': 'low',
                        'rollback': 'N/A (caches rebuild automatically)'
                    }
                ],
                'diagnostics': ['vmstat 1 5', 'free -m', 'sysctl vm.swappiness']
            },
            'excessive_paging': {
                'actions': [
                    {
                        'command': 'ps aux --sort=-rss | head -10',
                        'description': 'Find memory hogs causing paging',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'sysctl -w vm.swappiness=5',
                        'description': 'Minimize swapping',
                        'risk': 'low',
                        'rollback': 'sysctl -w vm.swappiness=60'
                    }
                ],
                'diagnostics': ['vmstat 1 5', 'free -m']
            },
            
            # ========================================
            # SCHEDULER - Context switching storms
            # ========================================
            'scheduler_thrashing': {
                'actions': [
                    {
                        'command': 'vmstat 1 5',
                        'description': 'Monitor context switches',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'taskset -p 0-3 {pid}',
                        'description': 'Limit CPU affinity',
                        'risk': 'low',
                        'rollback': 'taskset -p 0-7 {pid}'
                    }
                ],
                'diagnostics': ['vmstat 1 5', 'pidstat -w 1 5', 'ps -eLf | wc -l']
            },
            'high_context_switches': {
                'actions': [
                    {
                        'command': 'pidstat -w 1 5',
                        'description': 'Identify processes with high context switches',
                        'risk': 'none',
                        'rollback': 'N/A'
                    }
                ],
                'diagnostics': ['vmstat 1 5', 'pidstat -w 1 5']
            },
            
            # ========================================
            # SYSCALL - High latency syscalls
            # ========================================
            'syscall_latency': {
                'actions': [
                    {
                        'command': 'lsof -p {pid}',
                        'description': 'Check open files for blocking I/O',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'ionice -c2 -n5 -p {pid}',
                        'description': 'Adjust I/O priority',
                        'risk': 'low',
                        'rollback': 'ionice -c2 -n0 -p {pid}'
                    }
                ],
                'diagnostics': ['lsof -p {pid}', 'strace -c -p {pid} (requires root)']
            },
            
            # ========================================
            # PAGE FAULT - Excessive faulting
            # ========================================
            'page_fault_storm': {
                'actions': [
                    {
                        'command': 'ps -p {pid} -o pid,min_flt,maj_flt,comm',
                        'description': 'Check fault rates',
                        'risk': 'none',
                        'rollback': 'N/A'
                    },
                    {
                        'command': 'sysctl -w vm.swappiness=10',
                        'description': 'Reduce swapping',
                        'risk': 'low',
                        'rollback': 'sysctl -w vm.swappiness=60'
                    }
                ],
                'diagnostics': ['ps -p {pid} -o pid,min_flt,maj_flt,comm', 'vmstat 1 5']
            },
            
            # ========================================
            # GENERAL / UNKNOWN
            # ========================================
            'unknown_degradation': {
                'actions': [
                    {
                        'command': 'top -b -n 1',
                        'description': 'General system overview',
                        'risk': 'none',
                        'rollback': 'N/A'
                    }
                ],
                'diagnostics': ['top -b -n 1', 'ps aux', 'vmstat 1 5', 'free -m', 'iostat -x 1 5']
            }
        }
        
        recommendation = action_catalog.get(failure_mode, {
            'actions': [],
            'diagnostics': ['ps aux', 'top -b -n 1'],
            'note': f'No specific actions cataloged for {failure_mode}'
        })
        
        recommendation['failure_mode'] = failure_mode
        recommendation['urgency'] = urgency
        recommendation['affected_entity'] = affected_entity
        
        return recommendation
    
    def execute_remediation(self,
                           action_type: str,
                           params: Optional[Dict] = None,
                           justification: str = "",
                           expected_effect: str = "",
                           confidence: float = 0.0,
                           dry_run: bool = False) -> Dict:
        """
        Execute structured remediation action (Tool 5 - HYBRID MODEL).
        
        This is the GOLD STANDARD approach:
        - Gemini proposes ACTION TYPES (not raw commands)
        - System maps action_type → concrete command
        - Deterministic safety through structured execution
        
        Args:
            action_type: Structured action (e.g., "lower_process_priority")
            params: Action parameters (e.g., {"pid": 1234, "priority": 10})
            justification: Why this action needed
            expected_effect: What should happen
            confidence: Agent's confidence (0.0-1.0)
            dry_run: If True, validate only, don't execute
            
        Returns:
            {
                'valid': True/False,
                'executed': True/False,
                'command': "...",  # Actual command built from template
                'stdout': "...",
                'exit_code': 0,
                'action_result': {...}
            }
        """
        # Import action schema
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from action_schema import ActionType, build_command
        from policy_engine import execute_in_sandbox
        
        params = params or {}
        
        # Convert string to ActionType enum
        try:
            action_enum = ActionType(action_type)
        except ValueError:
            return {
                'valid': False,
                'error': f'Unknown action type: {action_type}',
                'available_actions': [a.value for a in ActionType]
            }
        
        # Build concrete command from action type
        build_result = build_command(action_enum, params)
        
        if not build_result['valid']:
            logger.warning(f"Invalid action parameters: {build_result['errors']}")
            return {
                'valid': False,
                'errors': build_result['errors'],
                'action_type': action_type,
                'params': params
            }
        
        command = build_result['command']
        risk = build_result['risk']
        description = build_result['description']
        rollback = build_result['rollback']
        
        # Log action proposal
        logger.info(f"Action proposed: {action_type}")
        logger.info(f"  Command: {command}")
        logger.info(f"  Risk: {risk}")
        logger.info(f"  Justification: {justification}")
        logger.info(f"  Expected effect: {expected_effect}")
        logger.info(f"  Confidence: {confidence:.2f}")
        
        # Dry run mode
        if dry_run:
            return {
                'valid': True,
                'executed': False,
                'dry_run': True,
                'action_type': action_type,
                'command': command,
                'risk': risk,
                'description': description,
                'rollback': rollback,
                'message': f"Action would be executed (risk: {risk})"
            }
        
        # Execute command
        logger.info(f"Executing action: {action_type}")
        
        try:
            result = execute_in_sandbox(command, timeout=30)
            
            return {
                'valid': True,
                'executed': True,
                'action_type': action_type,
                'command': command,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode,
                'success': result.returncode == 0,
                'risk': risk,
                'description': description,
                'rollback': rollback,
                'audit': {
                    'action_type': action_type,
                    'parameters': params,
                    'justification': justification,
                    'expected_effect': expected_effect,
                    'confidence': confidence,
                    'risk': risk
                }
            }
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                'valid': True,
                'executed': False,
                'error': str(e),
                'action_type': action_type,
                'command': command,
                'audit': {
                    'justification': justification,
                    'expected_effect': expected_effect
                }
            }
    
    def close(self):
        """Close database connections."""
        if self.conn:
            self.conn.close()
        self.trend_analyzer.close()
        self.baseline_analyzer.close()


if __name__ == "__main__":
    # Test tools
    logging.basicConfig(level=logging.INFO)
    
    import sys
    if len(sys.argv) < 2:
        print("Usage: python agent_tools.py <db_path>")
        sys.exit(1)
    
    tools = AgentTools(sys.argv[1])
    
    print("\n=== Testing query_signals ===")
    result = tools.query_signals(limit=5)
    print(f"Found {result['signal_count']} signals")
    print(f"Summary: {result['summary']}")
    
    print("\n=== Testing summarize_trends ===")
    result = tools.summarize_trends(['memory_pressure', 'load_mismatch'], lookback_minutes=10000)
    print(f"Summary: {result['summary']}")
    
    print("\n=== Testing propose_action ===")
    result = tools.propose_action('oom_risk', 'high')
    print(f"Actions for {result['failure_mode']}:")
    for action in result['actions']:
        print(f"  - {action['description']} (risk: {action['risk']})")
    
    tools.close()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Enhanced Agent Tools - 7 custom tools for advanced diagnostics

This module implements the powerful tools identified in the implementation plan:
1. get_top_processes - Resource hog identification
2. query_historical_baseline - Context-aware anomaly detection
3. get_related_signals - Cascading failure analysis  
4. check_system_logs - Kernel/service log parsing
5. query_past_resolutions - Learning from history
6. get_disk_usage - Storage health check
7. validate_system_config - Configuration validation
"""

import sys
import os
import logging
import subprocess
import shutil
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

# Try to import psutil (for get_top_processes)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not available - get_top_processes will use fallback")


class EnhancedAgentTools:
    """
    Collection of enhanced diagnostic and remediation tools.
    
    Each tool returns structured data for Gemini to analyze.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize enhanced tools.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    # ========================================================================
    # PRIORITY 0: Critical Diagnostic Tools
    # ========================================================================
    
    def get_top_processes(self, metric: str = "cpu", limit: int = 10) -> Dict:
        """
        Get top resource-consuming processes.
        
        Args:
            metric: Resource to sort by ("cpu", "memory", "io")
            limit: Number of processes to return
        
        Returns:
            {
                "processes": [
                    {"pid": 1234, "name": "chrome", "cpu_percent": 45.2, 
                     "memory_mb": 2048, "user": "shadi"},
                    ...
                ],
                "total_processes": 150,
                "summary": "Top 10 by CPU"
            }
        """
        if not HAS_PSUTIL:
            return self._get_top_processes_fallback(metric, limit)
        
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'] or 'unknown',
                        'user': info['username'] or 'unknown',
                        'cpu_percent': info['cpu_percent'] or 0.0,
                        'memory_mb': (info['memory_info'].rss / 1024 / 1024) if info['memory_info'] else 0
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by requested metric
            if metric == "cpu":
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            elif metric == "memory":
                processes.sort(key=lambda x: x['memory_mb'], reverse=True)
            else:
                # Default to CPU
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            top_processes = processes[:limit]
            
            return {
                "processes": top_processes,
                "total_processes": len(processes),
                "metric": metric,
                "summary": f"Top {limit} processes by {metric}"
            }
            
        except Exception as e:
            logger.error(f"Error getting processes: {e}")
            return {"error": str(e), "processes": []}
    
    def _get_top_processes_fallback(self, metric: str, limit: int) -> Dict:
        """Fallback using 'ps' command when psutil unavailable"""
        try:
            # Use ps command
            cmd = ['ps', 'aux', '--sort=-%cpu' if metric == 'cpu' else '-%mem']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            processes = []
            
            for line in lines[:limit]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        'user': parts[0],
                        'pid': int(parts[1]),
                        'cpu_percent': float(parts[2]),
                        'memory_mb': float(parts[3]),  # Actually memory %
                        'name': parts[10][:30]
                    })
            
            return {
                "processes": processes,
                "total_processes": len(lines),
                "method": "ps_fallback",
                "summary": f"Top {limit} by {metric} (ps command)"
            }
        except Exception as e:
            return {"error": f"Both psutil and ps failed: {e}", "processes": []}
    
    def query_historical_baseline(self, 
                                  metric_type: str,
                                  lookback_hours: int = 24) -> Dict:
        """
        Compare current metrics to historical baseline.
        
        Args:
            metric_type: Type of metric ("memory", "cpu", "disk_io", "network")
            lookback_hours: Hours of history to analyze
        
        Returns:
            {
                "metric": "memory_usage",
                "current_value": 85.0,
                "baseline_mean": 42.0,
                "baseline_std": 5.0,
                "deviation_sigma": 8.6,  # Standard deviations from normal
                "is_abnormal": true,
                "confidence": 0.95
            }
        """
        try:
            # Determine which table to query
            table_map = {
                "memory": "memory_metrics",
                "cpu": "load_metrics",
                "disk_io": "block_stats",
                "network": "network_interface_stats"
            }
            
            table = table_map.get(metric_type, "memory_metrics")
            
            # Get historical data
            since_ts = int((datetime.now() - timedelta(hours=lookback_hours)).timestamp() * 1_000_000_000)
            
            if metric_type == "memory":
                query = """
                    SELECT 
                        (mem_total_kb - mem_available_kb) * 100.0 / mem_total_kb as usage_percent,
                        timestamp
                    FROM memory_metrics
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """
            elif metric_type == "cpu":
                query = """
                    SELECT load_1min as usage_percent, timestamp
                    FROM load_metrics
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """
            elif metric_type in ["disk_io", "io"]:
                query = """
                    SELECT read_ticks as usage_percent, timestamp
                    FROM block_stats
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """
            else:
                return {"error": f"Unsupported metric type: {metric_type}. Valid: cpu, memory, disk_io, io"}

            
            cursor = self.conn.execute(query, (since_ts,))
            rows = cursor.fetchall()
            
            if len(rows) < 10:
                return {
                    "error": "Insufficient historical data",
                    "data_points": len(rows),
                    "required": 10
                }
            
            # Calculate baseline statistics
            values = [row['usage_percent'] for row in rows if row['usage_percent'] is not None]
            
            if not values:
                return {"error": "No valid data points"}
            
            import statistics
            
            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) > 1 else 0
            current = values[0]  # Most recent
            
            # Calculate deviation in standard deviations (sigma)
            deviation_sigma = (current - mean) / std if std > 0 else 0
            
            # Abnormal if > 3 sigma from mean
            is_abnormal = abs(deviation_sigma) > 3.0
            
            return {
                "metric": metric_type,
                "current_value": round(current, 2),
                "baseline_mean": round(mean, 2),
                "baseline_std": round(std, 2),
                "deviation_sigma": round(deviation_sigma, 2),
                "is_abnormal": is_abnormal,
                "confidence": 0.95 if len(values) > 100 else 0.80,
                "data_points": len(values),
                "lookback_hours": lookback_hours
            }
            
        except Exception as e:
            logger.error(f"Baseline query error: {e}")
            return {"error": str(e)}
    
    def get_related_signals(self,
                           signal_id: Optional[int] = None,
                           signal_type: Optional[str] = None,
                           time_window_seconds: int = 300) -> Dict:
        """
        Find temporally correlated signals (cascading failures).
        
        Args:
            signal_id: ID of anchor signal (OR)
            signal_type: Type of anchor signal (if no ID)
            time_window_seconds: Time window to search (default 5 min)
        
        Returns:
            {
                "anchor_signal": {"type": "memory_pressure", "timestamp": ...},
                "related_signals": [
                    {"type": "io_latency_spike", "timestamp": ..., "time_delta_seconds": 30},
                    ...
                ],
                "cascade_detected": true,
                "cascade_chain": "memory_pressure → oom_kill → load_spike"
            }
        """
        try:
            # Get anchor signal
            if signal_id:
                anchor = self.conn.execute(
                    "SELECT * FROM signal_metadata WHERE id = ?", (signal_id,)
                ).fetchone()
            elif signal_type:
                anchor = self.conn.execute(
                    "SELECT * FROM signal_metadata WHERE signal_type = ? ORDER BY timestamp DESC LIMIT 1",
                    (signal_type,)
                ).fetchone()
            else:
                return {"error": "Must provide signal_id or signal_type"}
            
            if not anchor:
                return {"error": "Anchor signal not found"}
            
            # Find signals within time window
            anchor_ts = anchor['timestamp']
            window_start = anchor_ts - (time_window_seconds * 1_000_000_000)
            window_end = anchor_ts + (time_window_seconds * 1_000_000_000)
            
            query = """
                SELECT signal_type, severity, timestamp, summary
                FROM signal_metadata
                WHERE timestamp BETWEEN ? AND ?
                  AND timestamp != ?
                ORDER BY timestamp ASC
            """
            
            cursor = self.conn.execute(query, (window_start, window_end, anchor_ts))
            related = cursor.fetchall()
            
            related_signals = []
            for sig in related:
                time_delta = (sig['timestamp'] - anchor_ts) / 1_000_000_000  # Convert to seconds
                related_signals.append({
                    'type': sig['signal_type'],
                    'severity': sig['severity'],
                    'time_delta_seconds': round(time_delta, 1),
                    'summary': sig['summary']
                })
            
            # Detect cascade pattern (simple heuristic)
            cascade_detected = len(related_signals) >= 2
            
            # Build cascade chain
            if cascade_detected:
                chain_types = [anchor['signal_type']] + [s['type'] for s in related_signals[:3]]
                cascade_chain = " → ".join(chain_types)
            else:
                cascade_chain = None
            
            return {
                "anchor_signal": {
                    "type": anchor['signal_type'],
                    "timestamp": anchor['timestamp'],
                    "severity": anchor['severity']
                },
                "related_signals": related_signals,
                "total_related": len(related_signals),
                "time_window_seconds": time_window_seconds,
                "cascade_detected": cascade_detected,
                "cascade_chain": cascade_chain
            }
            
        except Exception as e:
            logger.error(f"Related signals error: {e}")
            return {"error": str(e)}
    
    # ========================================================================
    # PRIORITY 1: Enhanced Context Tools
    # ========================================================================
    
    def check_system_logs(self,
                         source: str = "dmesg",
                         keywords: Optional[List[str]] = None,
                         since_minutes: int = 30,
                         limit: int = 50) -> Dict:
        """
        Search system logs for error patterns.
        
        Args:
            source: Log source ("dmesg", "journalctl", "syslog")
            keywords: Keywords to search for (default: ["error", "fail", "oom"])
            since_minutes: How far back to search
            limit: Max entries to return
        
        Returns:
            {
                "source": "dmesg",
                "entries": [
                    {"timestamp": "...", "level": "error", "message": "..."},
                    ...
                ],
                "total_matches": 5,
                "summary": "OOM killer invoked, killed java process"
            }
        """
        if keywords is None:
            keywords = ["error", "fail", "oom", "killed", "segfault"]
        
        entries = []
        
        try:
            if source == "dmesg":
                # Use dmesg command
                cmd = ['dmesg', '-T']  # Human-readable timestamps
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                for line in result.stdout.strip().split('\n'):
                    # Check if any keyword matches
                    if any(kw.lower() in line.lower() for kw in keywords):
                        # Parse timestamp and message
                        parts = line.split(']', 1)
                        if len(parts) == 2:
                            timestamp = parts[0].lstrip('[')
                            message = parts[1].strip()
                            
                            # Determine level
                            level = "error" if "error" in message.lower() else "warn"
                            
                            entries.append({
                                "timestamp": timestamp,
                                "level": level,
                                "message": message[:200]  # Truncate long messages
                            })
                
                entries = entries[-limit:]  # Last N entries
                
            elif source == "journalctl":
                # Use journalctl
                cmd = ['journalctl', '--since', f'{since_minutes} minutes ago', '-p', 'err', '-n', str(limit)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                for line in result.stdout.strip().split('\n'):
                    if line and any(kw.lower() in line.lower() for kw in keywords):
                        entries.append({
                            "timestamp": "recent",
                            "level": "error",
                            "message": line[:200]
                        })
            
            else:
                return {"error": f"Unsupported log source: {source}"}
            
            # Generate summary
            if entries:
                # Simple summary: most common error type
                oom_count = sum(1 for e in entries if 'oom' in e['message'].lower())
                killed_count = sum(1 for e in entries if 'killed' in e['message'].lower())
                
                if oom_count > 0:
                    summary = f"OOM killer active: {oom_count} events"
                elif killed_count > 0:
                    summary = f"Process kills detected: {killed_count} events"
                else:
                    summary = f"Found {len(entries)} error entries"
            else:
                summary = "No matching log entries found"
            
            return {
                "source": source,
                "entries": entries,
                "total_matches": len(entries),
                "keywords_searched": keywords,
                "summary": summary
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Log command timed out"}
        except Exception as e:
            logger.error(f"Log check error: {e}")
            return {"error": str(e)}
    
    def query_past_resolutions(self,
                               signal_type: str,
                               lookback_days: int = 30) -> Dict:
        """
        Learn from historical action effectiveness.
        
        Args:
            signal_type: Signal type to analyze
            lookback_days: Days of history to analyze
        
        Returns:
            {
                "signal_type": "memory_pressure",
                "total_occurrences": 47,
                "actions_taken": [
                    {"action": "clear_page_cache", "count": 23, 
                     "success_rate": 0.87, "avg_resolution_time_seconds": 45},
                    ...
                ],
                "recommendation": "kill_process (highest success + fastest)"
            }
        """
        # Note: This requires an action_history table that we'll create
        # For now, return mock data based on common patterns
        
        # Check if action_history table exists
        try:
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='action_history'"
            )
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # Return heuristic-based recommendations
                recommendations = {
                    "memory_pressure": [
                        {"action": "clear_page_cache", "success_rate": 0.85, "avg_time": 45},
                        {"action": "kill_process", "success_rate": 0.90, "avg_time": 5},
                    ],
                    "load_mismatch": [
                        {"action": "renice_process", "success_rate": 0.70, "avg_time": 10},
                    ],
                    "io_latency_spike": [
                        {"action": "clear_page_cache", "success_rate": 0.60, "avg_time": 50},
                    ]
                }
                
                actions = recommendations.get(signal_type, [])
                
                if actions:
                    best_action = max(actions, key=lambda x: x['success_rate'])
                    recommendation = f"{best_action['action']} (success rate: {best_action['success_rate']*100}%)"
                else:
                    recommendation = "No historical data available"
                
                return {
                    "signal_type": signal_type,
                    "total_occurrences": "unknown",
                    "actions_taken": actions,
                    "recommendation": recommendation,
                    "note": "Using heuristics - action_history table not found"
                }
            
            # If table exists, query it
            # TODO: Implement actual historical analysis
            return {
                "signal_type": signal_type,
                "note": "Historical analysis not yet implemented"
            }
            
        except Exception as e:
            logger.error(f"Past resolutions error: {e}")
            return {"error": str(e)}
    
    # ========================================================================
    # PRIORITY 2: Preventive & Advanced Tools
    # ========================================================================
    
    def get_disk_usage(self) -> Dict:
        """
        Get disk space and inode usage for all mount points.
        
        Returns:
            {
                "filesystems": [
                    {"mount": "/", "used_percent": 78, "available_gb": 12.3, 
                     "inodes_used_percent": 45},
                    {"mount": "/var", "used_percent": 98, "available_gb": 0.5, 
                     "inodes_used_percent": 92, "status": "CRITICAL"}
                ],
                "critical": ["/var"],
                "warnings": ["/home"]
            }
        """
        try:
            filesystems = []
            critical = []
            warnings = []
            
            # Get all mount points
            partitions = []
            try:
                with open('/proc/mounts', 'r') as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            device, mount = parts[0], parts[1]
                            # Skip special filesystems
                            if not mount.startswith(('/proc', '/sys', '/dev', '/run')):
                                partitions.append(mount)
            except:
                partitions = ['/']  # Fallback to root
            
            for mount in partitions:
                try:
                    stat = shutil.disk_usage(mount)
                    
                    used_percent = (stat.used / stat.total) * 100 if stat.total > 0 else 0
                    available_gb = stat.free / (1024**3)
                    
                    fs_info = {
                        "mount": mount,
                        "used_percent": round(used_percent, 1),
                        "available_gb": round(available_gb, 2),
                        "total_gb": round(stat.total / (1024**3), 2)
                    }
                    
                    # Determine status
                    if used_percent >= 95:
                        fs_info["status"] = "CRITICAL"
                        critical.append(mount)
                    elif used_percent >= 85:
                        fs_info["status"] = "WARNING"
                        warnings.append(mount)
                    else:
                        fs_info["status"] = "OK"
                    
                    filesystems.append(fs_info)
                    
                except Exception as e:
                    logger.warning(f"Could not stat {mount}: {e}")
            
            return {
                "filesystems": filesystems,
                "critical": critical,
                "warnings": warnings,
                "total_checked": len(filesystems)
            }
            
        except Exception as e:
            logger.error(f"Disk usage error: {e}")
            return {"error": str(e)}
    
    def validate_system_config(self, category: str = "all") -> Dict:
        """
        Validate system parameters against best practices.
        
        Args:
            category: Category to check ("all", "memory", "network", "io")
        
        Returns:
            {
                "checks": [
                    {"parameter": "vm.swappiness", "current": 60, "recommended": 10,
                     "severity": "medium", "rationale": "..."},
                    ...
                ],
                "issues_found": 2,
                "suggested_fixes": ["sysctl -w vm.swappiness=10", ...]
            }
        """
        try:
            checks = []
            suggested_fixes = []
            
            # Define best practice rules
            best_practices = {
                "vm.swappiness": {
                    "recommended": 10,
                    "severity": "medium",
                    "rationale": "High swappiness causes unnecessary disk I/O on systems with adequate RAM"
                },
                "vm.dirty_ratio": {
                    "recommended": 10,
                    "severity": "low",
                    "rationale": "Lower dirty_ratio prevents large write bursts"
                },
                "net.core.somaxconn": {
                    "recommended": 1024,
                    "severity": "high",
                    "rationale": "Low connection backlog can cause dropped connections under load"
                },
                "net.ipv4.tcp_max_syn_backlog": {
                    "recommended": 2048,
                    "severity": "medium",
                    "rationale": "Prevents SYN flood vulnerabilities"
                }
            }
            
            # Filter by category
            if category == "memory":
                params = {k: v for k, v in best_practices.items() if k.startswith('vm.')}
            elif category == "network":
                params = {k: v for k, v in best_practices.items() if k.startswith('net.')}
            else:
                params = best_practices
            
            # Check each parameter
            for param, config in params.items():
                try:
                    # Read current value
                    result = subprocess.run(
                        ['sysctl', '-n', param],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        current = int(result.stdout.strip())
                        recommended = config['recommended']
                        
                        if current != recommended:
                            checks.append({
                                "parameter": param,
                                "current": current,
                                "recommended": recommended,
                                "severity": config['severity'],
                                "rationale": config['rationale']
                            })
                            
                            suggested_fixes.append(f"sysctl -w {param}={recommended}")
                    
                except Exception as e:
                    logger.debug(f"Could not check {param}: {e}")
            
            return {
                "checks": checks,
                "issues_found": len(checks),
                "suggested_fixes": suggested_fixes,
                "category": category
            }
            
        except Exception as e:
            logger.error(f"Config validation error: {e}")
            return {"error": str(e)}
    
    def execute_command(self,
                       command: str,
                       timeout_seconds: int = 30,
                       require_sudo: bool = False) -> Dict:
        """
        Execute a shell command and return the result.
        
        This is the remediation action tool - use it to actually fix issues.
        
        Args:
            command: Shell command to execute (e.g., "apt-get clean", "systemctl restart nginx")
            timeout_seconds: Max execution time (default 30)
            require_sudo: If True, prepend sudo to command
        
        Returns:
            {
                "command": "apt-get clean",
                "exit_code": 0,
                "stdout": "...",
                "stderr": "...",
                "success": true,
                "execution_time_ms": 1234
            }
        
        SAFETY: This tool should only be called after user approval.
        The interactive agent wrapper handles approval before execution.
        """
        import time
        
        start_time = time.time()
        
        try:
            # Optionally prepend sudo - use sh -c wrapper for proper shell operator handling
            if require_sudo and not command.startswith('sudo '):
                # Wrap in sh -c to handle redirects and && properly under sudo
                command = f"sudo sh -c '{command}'"
            
            logger.info(f"Executing command: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout[:2000] if result.stdout else "",  # Truncate large output
                "stderr": result.stderr[:500] if result.stderr else "",
                "success": result.returncode == 0,
                "execution_time_ms": execution_time_ms
            }
            
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout_seconds}s",
                "success": False,
                "execution_time_ms": timeout_seconds * 1000
            }
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "error": str(e)
            }


# Tool definitions for Gemini Interactions API (JSON schemas)
ENHANCED_TOOL_SCHEMAS = [

    {
        "type": "function",
        "name": "get_top_processes",
        "description": "Get top resource-consuming processes to identify specific resource hogs",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["cpu", "memory", "io"],
                    "description": "Resource metric to sort by"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of processes to return (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "query_historical_baseline",
        "description": "Compare current metrics to historical baseline to determine if state is abnormal for THIS system",
        "parameters": {
            "type": "object",
            "properties": {
                "metric_type": {
                    "type": "string",
                    "enum": ["memory", "cpu", "disk_io", "network"],
                    "description": "Type of metric to analyze"
                },
                "lookback_hours": {
                    "type": "integer",
                    "description": "Hours of history to analyze (default 24)"
                }
            },
            "required": ["metric_type"]
        }
    },
    {
        "type": "function",
        "name": "get_related_signals",
        "description": "Find temporally correlated signals to identify cascading failures and cause-effect chains",
        "parameters": {
            "type": "object",
            "properties": {
                "signal_type": {
                    "type": "string",
                    "description": "Type of anchor signal to find related signals for"
                },
                "time_window_seconds": {
                    "type": "integer",
                    "description": "Time window to search in seconds (default 300)"
                }
            },
            "required": ["signal_type"]
        }
    },
    {
        "type": "function",
        "name": "check_system_logs",
        "description": "Search system logs (dmesg, journalctl) for error patterns. PARAMS: source (dmesg|journalctl), keywords (array of strings to search for), since_minutes, limit. Do NOT use 'query' param - use 'keywords' instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["dmesg", "journalctl"],
                    "description": "Log source to search (default: dmesg)"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to search for like ['disk', 'space', 'full']. Default: ['error', 'fail', 'oom']"
                },
                "since_minutes": {
                    "type": "integer",
                    "description": "How far back to search (default: 30)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default: 50)"
                }
            },
            "required": []
        }
    },

    {
        "type": "function",
        "name": "query_past_resolutions",
        "description": "Learn which actions worked for similar issues in the past. REQUIRED: signal_type (e.g., 'memory_pressure', 'disk_space_warning', 'cpu_saturation'). Optional: lookback_days.",
        "parameters": {
            "type": "object",
            "properties": {
                "signal_type": {
                    "type": "string",
                    "description": "REQUIRED - Signal type like 'memory_pressure', 'disk_space_warning', 'io_congestion'"
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Days of history to analyze (default: 30)"
                }
            },
            "required": ["signal_type"]
        }
    },

    {
        "type": "function",
        "name": "get_disk_usage",
        "description": "Get disk space and inode usage for all mount points to detect storage issues",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "validate_system_config",
        "description": "Check system tuning parameters (sysctl) against best practices",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "memory", "network", "io"],
                    "description": "Category of parameters to check (default: all)"
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "execute_command",
        "description": "Execute a shell command to fix system issues. REQUIRES USER APPROVAL. Use for: apt-get clean, systemctl restart, journalctl --vacuum-time, etc. PARAMS: command (REQUIRED), timeout_seconds (default 30), require_sudo (default false).",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "REQUIRED - Shell command to execute, e.g., 'apt-get clean' or 'systemctl restart nginx'"
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default: 30)"
                },
                "require_sudo": {
                    "type": "boolean",
                    "description": "If true, prepend sudo to the command (default: false)"
                }
            },
            "required": ["command"]
        }
    }
]



# Tool definitions for Gemini Interactions API (JSON schemas)
ENHANCED_TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "get_top_processes",
        "description": "Get top resource-consuming processes to identify specific resource hogs",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["cpu", "memory", "io"],
                    "description": "Resource metric to sort by"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of processes to return (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "query_historical_baseline",
        "description": "Compare current metrics to historical baseline to determine if state is abnormal for THIS system",
        "parameters": {
            "type": "object",
            "properties": {
                "metric_type": {
                    "type": "string",
                    "enum": ["memory", "cpu", "disk_io", "network"],
                    "description": "Type of metric to analyze"
                },
                "lookback_hours": {
                    "type": "integer",
                    "description": "Hours of history to analyze (default 24)"
                }
            },
            "required": ["metric_type"]
        }
    },
    {
        "type": "function",
        "name": "get_related_signals",
        "description": "Find temporally correlated signals to identify cascading failures and cause-effect chains",
        "parameters": {
            "type": "object",
            "properties": {
                "signal_type": {
                    "type": "string",
                    "description": "Type of anchor signal to find related signals for"
                },
                "time_window_seconds": {
                    "type": "integer",
                    "description": "Time window to search in seconds (default 300)"
                }
            },
            "required": ["signal_type"]
        }
    }
]


if __name__ == "__main__":
    # Test enhanced tools
    logging.basicConfig(level=logging.INFO)
    
    tools = EnhancedAgentTools("data/kernelsight.db")
    
    print("Testing Enhanced Tools:\n")
   
    # Test 1: Top processes
    print("1. Top Processes (CPU):")
    result = tools.get_top_processes("cpu", 5)
    print(f"   Found {len(result.get('processes', []))} processes")
    
    # Test 2: Historical baseline
    print("\n2. Historical Baseline (Memory):")
    result = tools.query_historical_baseline("memory", 24)
    if 'error' not in result:
        print(f"   Current: {result['current_value']}%, Baseline: {result['baseline_mean']}%")
        print(f"   Deviation: {result['deviation_sigma']}σ, Abnormal: {result['is_abnormal']}")
    
    # Test 3: Related signals
    print("\n3. Related Signals:")
    result = tools.get_related_signals(signal_type="memory_pressure", time_window_seconds=300)
    if 'error' not in result:
        print(f"   Found {result['total_related']} related signals")
        if result['cascade_detected']:
            print(f"   Cascade: {result['cascade_chain']}")

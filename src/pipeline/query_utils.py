#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Query utilities for KernelSight AI telemetry database.
Provides helper functions for common query patterns.
"""

import sys
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from db_manager import DatabaseManager

logger = logging.getLogger(__name__)


def get_timestamp_ns(dt: datetime) -> int:
    """Convert datetime to nanoseconds since epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def query_syscalls_by_timerange(
    db: DatabaseManager,
    start: datetime,
    end: datetime,
    min_latency_ms: Optional[float] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query syscall events within a time range.
    
    Args:
        db: Database manager
        start: Start time
        end: End time
        min_latency_ms: Minimum latency in milliseconds (optional filter)
        limit: Maximum number of results
        
    Returns:
        List of syscall events
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            pid, tid, comm, syscall_nr, syscall_name,
            latency_ns / 1000000.0 as latency_ms,
            ret_value, is_error
        FROM syscall_events
        WHERE timestamp BETWEEN ? AND ?
    """
    
    params = [start_ns, end_ns]
    
    if min_latency_ms:
        sql += " AND latency_ns >= ?"
        params.append(int(min_latency_ms * 1_000_000))
    
    sql += " ORDER BY latency_ns DESC LIMIT ?"
    params.append(limit)
    
    rows = db.query(sql, tuple(params))
    return [dict(row) for row in rows]


def query_memory_stats(
    db: DatabaseManager,
    start: datetime,
    end: datetime,
    sample_interval_sec: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query memory metrics within a time range.
    
    Args:
        db: Database manager
        start: Start time
        end: End time
        sample_interval_sec: Sample interval in seconds (for downsampling)
        
    Returns:
        List of memory metrics
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    if sample_interval_sec:
        # Downsample by grouping into intervals
        sql = """
            SELECT 
                datetime(timestamp/1000000000, 'unixepoch') as time,
                AVG(mem_available_kb) as mem_available_kb,
                AVG(mem_free_kb) as mem_free_kb,
                AVG(cached_kb) as cached_kb,
                AVG(buffers_kb) as buffers_kb,
                AVG(dirty_kb) as dirty_kb,
                AVG(swap_total_kb - swap_free_kb) as swap_used_kb
            FROM memory_metrics
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY timestamp / (? * 1000000000)
            ORDER BY timestamp
        """
        params = (start_ns, end_ns, sample_interval_sec)
    else:
        sql = """
            SELECT 
                datetime(timestamp/1000000000, 'unixepoch') as time,
                mem_total_kb, mem_available_kb, mem_free_kb,
                buffers_kb, cached_kb, swap_total_kb, swap_free_kb,
                active_kb, inactive_kb, dirty_kb, writeback_kb
            FROM memory_metrics
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        params = (start_ns, end_ns)
    
    rows = db.query(sql, params)
    return [dict(row) for row in rows]


def query_io_latency_percentiles(
    db: DatabaseManager,
    start: datetime,
    end: datetime
) -> List[Dict[str, Any]]:
    """
    Query I/O latency percentiles within a time range.
    
    Args:
        db: Database manager
        start: Start time
        end: End time
        
    Returns:
        List of I/O latency statistics
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            read_count, write_count,
            read_bytes / 1024.0 / 1024.0 as read_mb,
            write_bytes / 1024.0 / 1024.0 as write_mb,
            read_p50_us, read_p95_us, read_p99_us, read_max_us,
            write_p50_us, write_p95_us, write_p99_us, write_max_us
        FROM io_latency_stats
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    
    rows = db.query(sql, (start_ns, end_ns))
    return [dict(row) for row in rows]


def query_network_bandwidth(
    db: DatabaseManager,
    interface: str,
    start: datetime,
    end: datetime
) -> List[Dict[str, Any]]:
    """
    Query network bandwidth for a specific interface.
    
    Args:
        db: Database manager
        interface: Interface name (e.g., 'eth0')
        start: Start time
        end: End time
        
    Returns:
        List of network statistics
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            rx_bytes / 1024.0 / 1024.0 as rx_mb,
            tx_bytes / 1024.0 / 1024.0 as tx_mb,
            rx_packets, tx_packets,
            rx_errors, tx_errors,
            rx_drops, tx_drops
        FROM network_interface_stats
        WHERE interface_name = ?
          AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    
    rows = db.query(sql, (interface, start_ns, end_ns))
    return [dict(row) for row in rows]


def query_top_processes_by_syscall_latency(
    db: DatabaseManager,
    start: datetime,
    end: datetime,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Query top processes by syscall latency.
    
    Args:
        db: Database manager
        start: Start time
        end: End time
        limit: Number of top processes to return
        
    Returns:
        List of processes with aggregated syscall stats
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            comm,
            pid,
            COUNT(*) as syscall_count,
            AVG(latency_ns) / 1000000.0 as avg_latency_ms,
            MAX(latency_ns) / 1000000.0 as max_latency_ms,
            SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as error_count
        FROM syscall_events
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY comm, pid
        ORDER BY avg_latency_ms DESC
        LIMIT ?
    """
    
    rows = db.query(sql, (start_ns, end_ns, limit))
    return [dict(row) for row in rows]


def query_block_io_summary(
    db: DatabaseManager,
    device: str,
    start: datetime,
    end: datetime
) -> List[Dict[str, Any]]:
    """
    Query block I/O summary for a device.
    
    Args:
        db: Database manager
        device: Device name (e.g., 'sda')
        start: Start time
        end: End time
        
    Returns:
        List of block I/O statistics
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            read_ios, write_ios,
            read_sectors * 512 / 1024.0 / 1024.0 as read_mb,
            write_sectors * 512 / 1024.0 / 1024.0 as write_mb,
            in_flight,
            CASE WHEN read_ios > 0 THEN read_ticks * 1.0 / read_ios ELSE 0 END as avg_read_latency_ms,
            CASE WHEN write_ios > 0 THEN write_ticks * 1.0 / write_ios ELSE 0 END as avg_write_latency_ms
        FROM block_stats
        WHERE device_name = ?
          AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    
    rows = db.query(sql, (device, start_ns, end_ns))
    return [dict(row) for row in rows]


def query_tcp_connection_summary(
    db: DatabaseManager,
    start: datetime,
    end: datetime
) -> List[Dict[str, Any]]:
    """
    Query TCP connection state summary.
    
    Args:
        db: Database manager
        start: Start time
        end: End time
        
    Returns:
        List of TCP connection statistics
    """
    start_ns = get_timestamp_ns(start)
    end_ns = get_timestamp_ns(end)
    
    sql = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            established, listen,
            syn_sent, syn_recv,
            time_wait, close_wait,
            fin_wait1, fin_wait2,
            established + syn_sent + syn_recv + fin_wait1 + fin_wait2 + 
                time_wait + close + close_wait + last_ack + listen + closing as total_connections
        FROM tcp_stats
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    
    rows = db.query(sql, (start_ns, end_ns))
    return [dict(row) for row in rows]


def demo_queries(db_path: str = "data/kernelsight.db"):
    """Run demo queries to show database contents."""
    db = DatabaseManager(db_path)
    
    print("=== KernelSight AI Query Utility Demo ===\n")
    
    # Show table statistics
    print("Table Statistics:")
    stats = db.get_table_stats()
    for table, count in sorted(stats.items()):
        if count > 0:
            print(f"  {table}: {count} rows")
    print()
    
    # Query recent data (last hour)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    # Top syscalls by latency
    print("Top 5 Slowest Syscalls (last hour):")
    syscalls = query_syscalls_by_timerange(db, start_time, end_time, limit=5)
    for sc in syscalls:
        print(f"  {sc['time']} | PID {sc['pid']} ({sc['comm']}) | "
              f"{sc['syscall_name']}: {sc['latency_ms']:.2f}ms")
    print()
    
    # Recent memory stats
    print("Recent Memory Stats (last 5 samples):")
    memory = query_memory_stats(db, start_time, end_time)
    for mem in memory[-5:]:
        if 'mem_available_kb' in mem:
            used_pct = 100 - (mem['mem_available_kb'] / (mem.get('mem_total_kb', 1) or 1) * 100)
            print(f"  {mem['time']} | Available: {mem['mem_available_kb']/1024:.0f}MB | "
                  f"Used: {used_pct:.1f}%")
    print()
    
    # I/O latency
    print("Recent I/O Latency (last 5 samples):")
    io_stats = query_io_latency_percentiles(db, start_time, end_time)
    for io in io_stats[-5:]:
        print(f"  {io['time']} | Reads: {io['read_count']}, Writes: {io['write_count']} | "
              f"P95: R={io['read_p95_us']:.1f}us, W={io['write_p95_us']:.1f}us")
    print()
    
    db.close()


def main():
    """Main entry point for query utility."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="KernelSight AI Query Utility")
    parser.add_argument('--db-path', default='data/kernelsight.db', help='Database path')
    parser.add_argument('--demo', action='store_true', help='Run demo queries')
    
    args = parser.parse_args()
    
    if args.demo:
        demo_queries(args.db_path)
    else:
        print("Use --demo to run demo queries")
        print("Or import this module to use query functions programmatically")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

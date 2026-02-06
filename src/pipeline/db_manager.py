#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Database manager for KernelSight AI telemetry storage.
Handles SQLite connection, schema initialization, and data operations.
"""

import sqlite3
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database connection and operations."""
    
    def __init__(self, db_path: str = "data/kernelsight.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_directory()
        self._connect()
    
    def _ensure_directory(self):
        """Create database directory if it doesn't exist."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory: {db_dir.absolute()}")
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
            # Enable WAL mode for better concurrent access
            self.conn.execute("PRAGMA journal_mode=WAL")
            # Optimize for bulk inserts
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def init_schema(self):
        """Initialize database schema from SQL file."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            self.conn.executescript(schema_sql)
            self.conn.commit()
            logger.info("Database schema initialized successfully")
            
            # Log schema version
            version = self.conn.execute(
                "SELECT version, description FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if version:
                logger.info(f"Schema version: {version['version']} - {version['description']}")
        
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise
    
    def insert_syscall_event(self, event: Dict[str, Any]):
        """Insert a syscall event."""
        # Handle field name mapping: syscall tracer outputs latency_ms, DB expects latency_ns
        latency_ns = event.get('latency_ns')
        if latency_ns is None and 'latency_ms' in event:
            # Convert milliseconds to nanoseconds
            latency_ns = int(event['latency_ms'] * 1_000_000)
        
        sql = """
            INSERT INTO syscall_events 
            (timestamp, pid, tid, cpu, uid, syscall_nr, syscall_name, 
             latency_ns, ret_value, is_error, arg0, comm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event.get('timestamp'),
            event.get('pid'),
            event.get('tid'),
            event.get('cpu'),
            event.get('uid'),
            event.get('syscall'),
            event.get('syscall_name'),
            latency_ns,
            event.get('ret_value'),
            1 if event.get('is_error') else 0,
            event.get('arg0'),
            event.get('comm', '')[:16]  # Truncate to 16 chars
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    

    def insert_page_fault_event(self, event: Dict[str, Any]):
        """Insert a page fault event."""
        sql = """
            INSERT INTO page_fault_events
            (timestamp, pid, tid, cpu, address, latency_ns, 
             fault_type, access_type, user_mode, comm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event.get('timestamp'),
            event.get('pid'),
            event.get('tid'),
            event.get('cpu'),
            event.get('address'),
            event.get('latency_ns'),
            event.get('fault_type'),
            event.get('access_type'),
            1 if event.get('user_mode') else 0,
            event.get('comm', '')[:16]
        )
        self.conn.execute(sql, params)
    
    def insert_io_latency_stats(self, stats: Dict[str, Any]):
        """Insert I/O latency statistics."""
        sql = """
            INSERT INTO io_latency_stats
            (timestamp, read_count, write_count, read_bytes, write_bytes,
             read_p50_us, read_p95_us, read_p99_us, read_max_us,
             write_p50_us, write_p95_us, write_p99_us, write_max_us)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            stats.get('timestamp'),
            stats.get('read_count', 0),
            stats.get('write_count', 0),
            stats.get('read_bytes', 0),
            stats.get('write_bytes', 0),
            stats.get('read_p50_us'),
            stats.get('read_p95_us'),
            stats.get('read_p99_us'),
            stats.get('read_max_us'),
            stats.get('write_p50_us'),
            stats.get('write_p95_us'),
            stats.get('write_p99_us'),
            stats.get('write_max_us')
        )
        self.conn.execute(sql, params)
    
    def insert_memory_metrics(self, metrics: Dict[str, Any]):
        """Insert memory metrics."""
        sql = """
            INSERT INTO memory_metrics
            (timestamp, mem_total_kb, mem_free_kb, mem_available_kb,
             buffers_kb, cached_kb, swap_total_kb, swap_free_kb,
             active_kb, inactive_kb, dirty_kb, writeback_kb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            metrics.get('timestamp'),
            metrics.get('mem_total_kb'),
            metrics.get('mem_free_kb'),
            metrics.get('mem_available_kb'),
            metrics.get('buffers_kb'),
            metrics.get('cached_kb'),
            metrics.get('swap_total_kb'),
            metrics.get('swap_free_kb'),
            metrics.get('active_kb'),
            metrics.get('inactive_kb'),
            metrics.get('dirty_kb'),
            metrics.get('writeback_kb')
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_load_metrics(self, metrics: Dict[str, Any]):
        """Insert load average metrics."""
        sql = """
            INSERT INTO load_metrics
            (timestamp, load_1min, load_5min, load_15min,
             running_processes, total_processes, last_pid)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            metrics.get('timestamp'),
            metrics.get('load_1min'),
            metrics.get('load_5min'),
            metrics.get('load_15min'),
            metrics.get('running_processes'),
            metrics.get('total_processes'),
            metrics.get('last_pid')
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_block_stats(self, stats: Dict[str, Any]):
        """Insert block device statistics."""
        sql = """
            INSERT INTO block_stats
            (timestamp, device_name, read_ios, read_merges, read_sectors, read_ticks,
             write_ios, write_merges, write_sectors, write_ticks,
             in_flight, io_ticks, time_in_queue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            stats.get('timestamp'),
            stats.get('device_name') or stats.get('device'),  # Map from scraper's 'device' field
            stats.get('read_ios'),
            stats.get('read_merges'),
            stats.get('read_sectors'),
            stats.get('read_ticks_ms') or stats.get('read_ticks'),  # Map from scraper's _ms field
            stats.get('write_ios'),
            stats.get('write_merges'),
            stats.get('write_sectors'),
            stats.get('write_ticks_ms') or stats.get('write_ticks'),  # Map from scraper's _ms field
            stats.get('in_flight'),
            stats.get('io_ticks_ms') or stats.get('io_ticks'),  # Map from scraper's _ms field
            stats.get('time_in_queue_ms') or stats.get('time_in_queue')  # Map from scraper's _ms field
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_network_stats(self, stats: Dict[str, Any]):
        """Insert network interface statistics."""
        sql = """
            INSERT INTO network_interface_stats
            (timestamp, interface_name, rx_bytes, rx_packets, rx_errors, rx_drops,
             tx_bytes, tx_packets, tx_errors, tx_drops)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            stats.get('timestamp'),
            stats.get('interface_name') or stats.get('interface'),  # Map from scraper's 'interface' field
            stats.get('rx_bytes'),
            stats.get('rx_packets'),
            stats.get('rx_errors'),
            stats.get('rx_drops'),
            stats.get('tx_bytes'),
            stats.get('tx_packets'),
            stats.get('tx_errors'),
            stats.get('tx_drops')
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_tcp_stats(self, stats: Dict[str, Any]):
        """Insert TCP connection statistics."""
        sql = """
            INSERT INTO tcp_stats
            (timestamp, established, syn_sent, syn_recv, fin_wait1, fin_wait2,
             time_wait, close, close_wait, last_ack, listen, closing)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            stats.get('timestamp'),
            stats.get('established'),
            stats.get('syn_sent'),
            stats.get('syn_recv'),
            stats.get('fin_wait1'),
            stats.get('fin_wait2'),
            stats.get('time_wait'),
            stats.get('close'),
            stats.get('close_wait'),
            stats.get('last_ack'),
            stats.get('listen'),
            stats.get('closing')
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_tcp_retransmit_stats(self, stats: Dict[str, Any]):
        """Insert TCP retransmit statistics."""
        sql = """
            INSERT INTO tcp_retransmit_stats (timestamp, retrans_segs)
            VALUES (?, ?)
        """
        params = (stats.get('timestamp'), stats.get('retrans_segs'))
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def insert_sched_stats(self, stats: Dict[str, Any]):
        """Insert scheduler statistics."""
        sql = """
            INSERT INTO sched_events
            (timestamp, pid, comm, context_switches, voluntary_switches,
             involuntary_switches, wakeups, cpu_time_ms, avg_timeslice_us)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            stats.get('timestamp'),
            stats.get('pid'),
            stats.get('comm', '')[:16],  # Truncate to 16 chars
            stats.get('context_switches', 0),
            stats.get('voluntary_switches', 0),
            stats.get('involuntary_switches', 0),
            stats.get('wakeups', 0),
            stats.get('cpu_time_ms'),
            stats.get('avg_timeslice_us')
        )
        self.conn.execute(sql, params)
    
    def insert_sched_event(self, event: Dict[str, Any]) -> int:
        """Insert a scheduler event and return its ID.
        
        Note: sched_tracer outputs 'time_bucket' instead of 'timestamp',
        so we check for both field names.
        """
        sql = """
            INSERT INTO sched_events
            (timestamp, pid, comm, context_switches, voluntary_switches,
             involuntary_switches, wakeups, cpu_time_ms, avg_timeslice_us)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        # Handle both 'timestamp' and 'time_bucket' field names
        ts = event.get('timestamp') or event.get('time_bucket')
        params = (
            ts,
            event.get('pid'),
            event.get('comm', '')[:16],
            event.get('context_switches', 0),
            event.get('voluntary_switches', 0),
            event.get('involuntary_switches', 0),
            event.get('wakeups', 0),
            event.get('cpu_time_ms'),
            event.get('avg_timeslice_us')
        )
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def commit(self):
        """Commit current transaction."""
        self.conn.commit()
    
    def get_table_stats(self) -> Dict[str, int]:
        """Get row counts for all tables."""
        tables = [
            'syscall_events', 'page_fault_events', 'io_latency_stats', 'sched_events',
            'memory_metrics', 'load_metrics', 'block_stats', 
            'network_interface_stats', 'tcp_stats', 'tcp_retransmit_stats'
        ]
        
        stats = {}
        for table in tables:
            try:
                result = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[table] = result[0]
            except sqlite3.Error:
                stats[table] = -1
        
        return stats
    
    def query(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a SELECT query and return results.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            List of rows
        """
        cursor = self.conn.execute(sql, params)
        return cursor.fetchall()
    
    # ============================================================================
    # Signal Metadata Methods (Agent Memory Interface)
    # ============================================================================
    
    def insert_signal(self, signal: Dict[str, Any]) -> int:
        """Insert a semantic signal observation."""
        import json
        
        sql = """
            INSERT INTO signal_metadata
            (timestamp, signal_category, signal_type, scope,
             semantic_label, severity, pressure_score, summary,
             patterns, reasoning_hints, source_table, source_id,
             entity_type, entity_id, entity_name, context_json,
             first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        patterns_json = json.dumps(signal.get('patterns', [])) if signal.get('patterns') else None
        hints_json = json.dumps(signal.get('reasoning_hints', [])) if signal.get('reasoning_hints') else None
        context_json = json.dumps(signal.get('context', {})) if signal.get('context') else None
        
        params = (
            signal['timestamp'], signal.get('signal_category', 'symptom'),
            signal['signal_type'], signal.get('scope', 'system'),
            signal.get('semantic_label'), signal.get('severity'),
            signal.get('pressure_score'), signal['summary'],
            patterns_json, hints_json, signal['source_table'], signal['source_id'],
            signal.get('entity_type'), signal.get('entity_id'), signal.get('entity_name'),
            context_json, signal['timestamp'], signal['timestamp']
        )
        
        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid
    
    def query_signals(self, signal_type=None, severity=None, signal_category=None,
                     since_timestamp=None, until_timestamp=None, entity_id=None,
                     limit=100) -> List[Dict[str, Any]]:
        """Query signals with filters."""
        import json
        
        sql = "SELECT * FROM signal_metadata WHERE 1=1"
        params = []
        
        if signal_type:
            sql += " AND signal_type = ?"
            params.append(signal_type)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if signal_category:
            sql += " AND signal_category = ?"
            params.append(signal_category)
        if since_timestamp:
            sql += " AND timestamp >= ?"
            params.append(since_timestamp)
        if until_timestamp:
            sql += " AND timestamp <= ?"
            params.append(until_timestamp)
        if entity_id:
            sql += " AND entity_id = ?"
            params.append(entity_id)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(sql, tuple(params))
        rows = cursor.fetchall()
        
        signals = []
        for row in rows:
            signal = dict(row)
            if signal.get('patterns'):
                signal['patterns'] = json.loads(signal['patterns'])
            if signal.get('reasoning_hints'):
                signal['reasoning_hints'] = json.loads(signal['reasoning_hints'])
            if signal.get('context_json'):
                signal['context'] = json.loads(signal['context_json'])
                del signal['context_json']
            signals.append(signal)
        
        return signals
    
    def get_critical_signals(self, since_minutes=60, limit=20) -> List[Dict[str, Any]]:
        """Get recent critical/high severity signals."""
        import time, json
        since_ns = int((time.time() - since_minutes * 60) * 1_000_000_000)
        
        sql = """
            SELECT * FROM signal_metadata
            WHERE timestamp >= ? AND severity IN ('critical', 'high')
            ORDER BY severity DESC, timestamp DESC LIMIT ?
        """
        
        cursor = self.conn.execute(sql, (since_ns, limit))
        rows = cursor.fetchall()
        
        signals = []
        for row in rows:
            signal = dict(row)
            if signal.get('patterns'):
                signal['patterns'] = json.loads(signal['patterns'])
            if signal.get('reasoning_hints'):
                signal['reasoning_hints'] = json.loads(signal['reasoning_hints'])
            if signal.get('context_json'):
                signal['context'] = json.loads(signal['context_json'])
                del signal['context_json']
            signals.append(signal)
        
        return signals
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            self.commit()
        self.close()


if __name__ == "__main__":
    # Test database initialization
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    db = DatabaseManager("data/test.db")
    db.init_schema()
    
    print("\nTable statistics:")
    for table, count in db.get_table_stats().items():
        print(f"  {table}: {count} rows")
    
    db.close()
    print("\nDatabase initialized successfully!")

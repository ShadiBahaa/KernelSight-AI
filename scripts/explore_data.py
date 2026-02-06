#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Comprehensive Exploratory Data Analysis for KernelSight AI.

Analyzes stress_test.db and all log files to generate:
- Time series plots for all metric categories
- Correlation heatmaps
- Distribution plots
- Log analysis reports
"""

import sys
import argparse
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import re
from collections import defaultdict, Counter

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'pipeline'))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.gridspec import GridSpec

from db_manager import DatabaseManager

# Configure matplotlib for better plots
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LogAnalyzer:
    """Analyzes log files from the stress test."""
    
    def __init__(self, log_dir: Path):
        """Initialize log analyzer."""
        self.log_dir = log_dir
        self.results = {}
    
    def analyze_all(self) -> Dict[str, Any]:
        """Analyze all log files."""
        logger.info(f"Analyzing logs in {self.log_dir}")
        
        if not self.log_dir.exists():
            logger.warning(f"Log directory not found: {self.log_dir}")
            return {}
        
        # Analyze each log type
        self.results['ingestion'] = self._analyze_ingestion_log()
        self.results['scraper'] = self._analyze_scraper_log()
        self.results['syscall'] = self._analyze_ebpf_log('syscall.log')
        self.results['io'] = self._analyze_ebpf_log('io.log')
        self.results['pagefault'] = self._analyze_ebpf_log('pagefault.log')
        self.results['sched'] = self._analyze_ebpf_log('sched.log')
        
        return self.results
    
    def _read_log(self, filename: str) -> List[str]:
        """Read log file lines."""
        log_path = self.log_dir / filename
        if not log_path.exists():
            logger.warning(f"Log file not found: {log_path}")
            return []
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.readlines()
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
            return []
    
    def _analyze_ingestion_log(self) -> Dict[str, Any]:
        """Analyze ingestion daemon log."""
        lines = self._read_log('ingestion.log')
        if not lines:
            return {}
        
        result = {
            'total_lines': len(lines),
            'errors': [],
            'warnings': [],
            'batches_processed': 0,
            'events_ingested': 0,
            'event_types': Counter()
        }
        
        for line in lines:
            # Count errors and warnings
            if 'ERROR' in line:
                result['errors'].append(line.strip())
            elif 'WARNING' in line or 'WARN' in line:
                result['warnings'].append(line.strip())
            
            # Parse batch processing
            if 'Batch insert' in line or 'batch' in line.lower():
                result['batches_processed'] += 1
            
            # Parse event types
            if 'syscall_events' in line:
                result['event_types']['syscall'] += 1
            elif 'page_fault' in line:
                result['event_types']['page_fault'] += 1
            elif 'io_latency' in line:
                result['event_types']['io_latency'] += 1
            elif 'memory_metrics' in line:
                result['event_types']['memory'] += 1
            elif 'network' in line:
                result['event_types']['network'] += 1
        
        return result
    
    def _analyze_scraper_log(self) -> Dict[str, Any]:
        """Analyze scraper daemon log."""
        lines = self._read_log('scraper.log')
        if not lines:
            return {}
        
        result = {
            'total_lines': len(lines),
            'errors': [],
            'warnings': [],
            'collection_cycles': 0,
            'collectors_run': set()
        }
        
        for line in lines:
            if 'ERROR' in line:
                result['errors'].append(line.strip())
            elif 'WARNING' in line:
                result['warnings'].append(line.strip())
            
            # Count collection cycles
            if 'Collecting' in line or 'collected' in line.lower():
                result['collection_cycles'] += 1
            
            # Identify active collectors
            if 'memory' in line.lower():
                result['collectors_run'].add('memory')
            if 'network' in line.lower():
                result['collectors_run'].add('network')
            if 'block' in line.lower() or 'disk' in line.lower():
                result['collectors_run'].add('block')
            if 'tcp' in line.lower():
                result['collectors_run'].add('tcp')
        
        result['collectors_run'] = list(result['collectors_run'])
        return result
    
    def _analyze_ebpf_log(self, filename: str) -> Dict[str, Any]:
        """Analyze eBPF tracer log."""
        lines = self._read_log(filename)
        if not lines:
            return {}
        
        result = {
            'total_lines': len(lines),
            'errors': [],
            'warnings': [],
            'events_emitted': 0,
            'initialization_success': False
        }
        
        for line in lines:
            if 'ERROR' in line or 'error' in line.lower():
                result['errors'].append(line.strip())
            elif 'WARNING' in line or 'warn' in line.lower():
                result['warnings'].append(line.strip())
            
            # Check initialization
            if 'Successfully' in line or 'Listening' in line or 'Attached' in line:
                result['initialization_success'] = True
            
            # Count events (lines typically start with timestamp or JSON)
            if line.strip().startswith('{'):
                result['events_emitted'] += 1
        
        return result


class DataExplorer:
    """Explores and visualizes database contents."""
    
    def __init__(self, db_path: str, output_dir: Path):
        """Initialize data explorer."""
        self.db = DatabaseManager(db_path)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")
    
    def generate_all_reports(self):
        """Generate all EDA reports and visualizations."""
        logger.info("Starting comprehensive data exploration...")
        
        # 1. Database overview
        self.generate_overview_report()
        
        # 2. Time series plots for each metric category
        self.plot_memory_metrics()
        self.plot_load_metrics()
        self.plot_network_metrics()
        self.plot_tcp_metrics()
        self.plot_io_metrics()
        self.plot_syscall_metrics()
        self.plot_page_fault_metrics()
        
        # 3. Correlation analysis
        self.plot_correlation_heatmap()
        
        # 4. Distribution plots
        self.plot_distributions()
        
        logger.info("All visualizations generated!")
    
    def generate_overview_report(self):
        """Generate database overview statistics."""
        logger.info("Generating database overview...")
        
        stats = self.db.get_table_stats()
        total_events = sum(v for v in stats.values() if v > 0)
        
        # Create text report
        report_path = self.output_dir / 'database_overview.txt'
        with open(report_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("KernelSight AI - Database Overview\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Total Events: {total_events:,}\n\n")
            
            f.write("Event Types:\n")
            f.write("-" * 70 + "\n")
            for table, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    pct = (count / total_events * 100) if total_events > 0 else 0
                    f.write(f"  {table:30} {count:8,} rows ({pct:5.1f}%)\n")
                else:
                    f.write(f"  {table:30} NO DATA\n")
        
        logger.info(f"Overview report saved to {report_path}")
        
        # Create visualization of table sizes
        fig, ax = plt.subplots(figsize=(12, 6))
        tables = [t for t, c in stats.items() if c > 0]
        counts = [stats[t] for t in tables]
        
        bars = ax.barh(tables, counts, color='steelblue')
        ax.set_xlabel('Number of Events', fontsize=12)
        ax.set_title('Event Type Distribution', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        
        # Add count labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                   f'{int(width):,}', ha='left', va='center', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'event_distribution.png', dpi=150)
        plt.close()
        logger.info("Event distribution plot saved")
    
    def plot_memory_metrics(self):
        """Plot memory usage over time."""
        logger.info("Plotting memory metrics...")
        
        rows = self.db.query("""
            SELECT timestamp, mem_total_kb, mem_free_kb, mem_available_kb,
                   buffers_kb, cached_kb, active_kb, inactive_kb
            FROM memory_metrics
            ORDER BY timestamp
        """)
        
        if not rows:
            logger.warning("No memory metrics found")
            return
        
        timestamps = [r['timestamp'] for r in rows]
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Memory usage
        ax = axes[0]
        ax.plot(timestamps, [r['mem_total_kb']/1024/1024 for r in rows], label='Total', linewidth=2)
        ax.plot(timestamps, [r['mem_available_kb']/1024/1024 for r in rows], label='Available')
        ax.plot(timestamps, [r['mem_free_kb']/1024/1024 for r in rows], label='Free')
        ax.plot(timestamps, [r['cached_kb']/1024/1024 for r in rows], label='Cached')
        ax.set_ylabel('Memory (GB)', fontsize=11)
        ax.set_title('Memory Usage Over Time', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        # Memory utilization percentage
        ax = axes[1]
        mem_used_pct = [(1 - r['mem_available_kb']/r['mem_total_kb']) * 100 for r in rows]
        ax.plot(timestamps, mem_used_pct, color='red', linewidth=2)
        ax.fill_between(timestamps, mem_used_pct, alpha=0.3, color='red')
        ax.set_xlabel('Timestamp', fontsize=11)
        ax.set_ylabel('Memory Used %', fontsize=11)
        ax.set_title('Memory Utilization Percentage', fontsize=13, fontweight='bold')
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'memory_metrics.png', dpi=150)
        plt.close()
        logger.info("Memory metrics plot saved")
    
    def plot_load_metrics(self):
        """Plot system load metrics."""
        logger.info("Plotting load metrics...")
        
        rows = self.db.query("""
            SELECT timestamp, load_1min, load_5min, load_15min,
                   running_processes, total_processes
            FROM load_metrics
            ORDER BY timestamp
        """)
        
        if not rows:
            logger.warning("No load metrics found")
            return
        
        timestamps = [r['timestamp'] for r in rows]
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Load averages
        ax = axes[0]
        ax.plot(timestamps, [r['load_1min'] for r in rows], label='1 min', linewidth=2)
        ax.plot(timestamps, [r['load_5min'] for r in rows], label='5 min', linewidth=2)
        ax.plot(timestamps, [r['load_15min'] for r in rows], label='15 min', linewidth=2)
        ax.set_ylabel('Load Average', fontsize=11)
        ax.set_title('System Load Average', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        # Process counts
        ax = axes[1]
        ax.plot(timestamps, [r['running_processes'] for r in rows], 
               label='Running', color='green', linewidth=2)
        ax.plot(timestamps, [r['total_processes'] for r in rows], 
               label='Total', color='blue', linewidth=2)
        ax.set_xlabel('Timestamp', fontsize=11)
        ax.set_ylabel('Process Count', fontsize=11)
        ax.set_title('Process Statistics', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'load_metrics.png', dpi=150)
        plt.close()
        logger.info("Load metrics plot saved")
    
    def plot_network_metrics(self):
        """Plot network interface statistics."""
        logger.info("Plotting network metrics...")
        
        rows = self.db.query("""
            SELECT timestamp, interface_name,
                   rx_bytes, tx_bytes, rx_packets, tx_packets,
                   rx_errors, tx_errors, rx_drops, tx_drops
            FROM network_interface_stats
            ORDER BY timestamp
        """)
        
        if not rows:
            logger.warning("No network metrics found")
            return
        
        # Group by interface
        interfaces = {}
        for row in rows:
            iface = row['interface_name']
            if iface not in interfaces:
                interfaces[iface] = []
            interfaces[iface].append(row)
        
        for iface, data in interfaces.items():
            timestamps = [r['timestamp'] for r in data]
            
            fig, axes = plt.subplots(2, 1, figsize=(14, 10))
            
            # Throughput (bytes)
            ax = axes[0]
            rx_mb = [r['rx_bytes']/1024/1024 for r in data]
            tx_mb = [r['tx_bytes']/1024/1024 for r in data]
            ax.plot(timestamps, rx_mb, label='RX', color='blue', linewidth=2)
            ax.plot(timestamps, tx_mb, label='TX', color='red', linewidth=2)
            ax.set_ylabel('Data (MB)', fontsize=11)
            ax.set_title(f'Network Throughput - {iface}', fontsize=13, fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)
            
            # Errors and drops
            ax = axes[1]
            ax.plot(timestamps, [r['rx_errors'] for r in data], label='RX Errors', linewidth=2)
            ax.plot(timestamps, [r['tx_errors'] for r in data], label='TX Errors', linewidth=2)
            ax.plot(timestamps, [r['rx_drops'] for r in data], label='RX Drops', linewidth=2, linestyle='--')
            ax.plot(timestamps, [r['tx_drops'] for r in data], label='TX Drops', linewidth=2, linestyle='--')
            ax.set_xlabel('Timestamp', fontsize=11)
            ax.set_ylabel('Count', fontsize=11)
            ax.set_title('Network Errors and Drops', fontsize=13, fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)
            
            plt.tight_layout()
            safe_iface = iface.replace('/', '_')
            plt.savefig(self.output_dir / f'network_{safe_iface}.png', dpi=150)
            plt.close()
        
        logger.info("Network metrics plots saved")
    
    def plot_tcp_metrics(self):
        """Plot TCP connection state statistics."""
        logger.info("Plotting TCP metrics...")
        
        rows = self.db.query("""
            SELECT timestamp, established, listen, time_wait,
                   syn_sent, syn_recv, fin_wait1, fin_wait2,
                   close_wait, closing, last_ack
            FROM tcp_stats
            ORDER BY timestamp
        """)
        
        if not rows:
            logger.warning("No TCP metrics found")
            return
        
        timestamps = [r['timestamp'] for r in rows]
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Main states
        ax = axes[0]
        ax.plot(timestamps, [r['established'] for r in rows], label='ESTABLISHED', linewidth=2)
        ax.plot(timestamps, [r['listen'] for r in rows], label='LISTEN', linewidth=2)
        ax.plot(timestamps, [r['time_wait'] for r in rows], label='TIME_WAIT', linewidth=2)
        ax.set_ylabel('Connection Count', fontsize=11)
        ax.set_title('TCP Connection States (Main)', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        # Transitional states
        ax = axes[1]
        ax.plot(timestamps, [r['syn_sent'] for r in rows], label='SYN_SENT')
        ax.plot(timestamps, [r['syn_recv'] for r in rows], label='SYN_RECV')
        ax.plot(timestamps, [r['fin_wait1'] for r in rows], label='FIN_WAIT1')
        ax.plot(timestamps, [r['fin_wait2'] for r in rows], label='FIN_WAIT2')
        ax.plot(timestamps, [r['close_wait'] for r in rows], label='CLOSE_WAIT')
        ax.set_xlabel('Timestamp', fontsize=11)
        ax.set_ylabel('Connection Count', fontsize=11)
        ax.set_title('TCP Connection States (Transitional)', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'tcp_metrics.png', dpi=150)
        plt.close()
        logger.info("TCP metrics plot saved")
    
    def plot_io_metrics(self):
        """Plot I/O latency statistics."""
        logger.info("Plotting I/O metrics...")
        
        rows = self.db.query("""
            SELECT timestamp, read_count, write_count,
                   read_p50_us, read_p95_us, read_p99_us,
                   write_p50_us, write_p95_us, write_p99_us
            FROM io_latency_stats
            ORDER BY timestamp
        """)
        
        if not rows:
            logger.warning("No I/O latency metrics found")
            return
        
        timestamps = [r['timestamp'] for r in rows]
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        # Operation counts
        ax = axes[0]
        ax.plot(timestamps, [r['read_count'] for r in rows], label='Reads', linewidth=2)
        ax.plot(timestamps, [r['write_count'] for r in rows], label='Writes', linewidth=2)
        ax.set_ylabel('Operation Count', fontsize=11)
        ax.set_title('I/O Operation Counts', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        # Read latencies
        ax = axes[1]
        ax.plot(timestamps, [r['read_p50_us'] or 0 for r in rows], label='p50')
        ax.plot(timestamps, [r['read_p95_us'] or 0 for r in rows], label='p95', linewidth=2)
        ax.plot(timestamps, [r['read_p99_us'] or 0 for r in rows], label='p99', linewidth=2)
        ax.set_ylabel('Latency (μs)', fontsize=11)
        ax.set_title('Read Latency Percentiles', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        # Write latencies
        ax = axes[2]
        ax.plot(timestamps, [r['write_p50_us'] or 0 for r in rows], label='p50')
        ax.plot(timestamps, [r['write_p95_us'] or 0 for r in rows], label='p95', linewidth=2)
        ax.plot(timestamps, [r['write_p99_us'] or 0 for r in rows], label='p99', linewidth=2)
        ax.set_xlabel('Timestamp', fontsize=11)
        ax.set_ylabel('Latency (μs)', fontsize=11)
        ax.set_title('Write Latency Percentiles', fontsize=13, fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'io_metrics.png', dpi=150)
        plt.close()
        logger.info("I/O metrics plot saved")
    
    def plot_syscall_metrics(self):
        """Plot syscall event statistics."""
        logger.info("Plotting syscall metrics...")
        
        # Top syscalls by count
        rows = self.db.query("""
            SELECT syscall_name, COUNT(*) as count, 
                   AVG(latency_ns) / 1000000.0 as avg_latency_ms
            FROM syscall_events
            GROUP BY syscall_name
            ORDER BY count DESC
            LIMIT 15
        """)
        
        if not rows:
            logger.warning("No syscall events found")
            return
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Top syscalls by count
        ax = axes[0]
        syscalls = [r['syscall_name'] for r in rows]
        counts = [r['count'] for r in rows]
        bars = ax.barh(syscalls, counts, color='steelblue')
        ax.set_xlabel('Count', fontsize=11)
        ax.set_title('Top System Calls by Frequency', fontsize=13, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                   f'{int(width):,}', ha='left', va='center', fontsize=8)
        
        # Slowest syscalls (top 10 by average latency)
        slow_rows = self.db.query("""
            SELECT syscall_name, COUNT(*) as count,
                   AVG(latency_ns) / 1000000.0 as avg_latency_ms
            FROM syscall_events
            GROUP BY syscall_name
            HAVING count > 10
            ORDER BY avg_latency_ms DESC
            LIMIT 10
        """)
        
        ax = axes[1]
        syscalls = [r['syscall_name'] for r in slow_rows]
        latencies = [r['avg_latency_ms'] for r in slow_rows]
        bars = ax.barh(syscalls, latencies, color='coral')
        ax.set_xlabel('Average Latency (ms)', fontsize=11)
        ax.set_title('Slowest System Calls (by average latency)', fontsize=13, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                   f'{width:.2f}ms', ha='left', va='center', fontsize=8)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'syscall_metrics.png', dpi=150)
        plt.close()
        logger.info("Syscall metrics plot saved")
    
    def plot_page_fault_metrics(self):
        """Plot page fault event statistics."""
        logger.info("Plotting page fault metrics...")
        
        rows = self.db.query("""
            SELECT fault_type, COUNT(*) as count,
                   AVG(latency_ns) / 1000.0 as avg_latency_us
            FROM page_fault_events
            GROUP BY fault_type
        """)
        
        if not rows:
            logger.warning("No page fault events found")
            return
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Fault type distribution
        ax = axes[0]
        fault_types = [r['fault_type'] for r in rows]
        counts = [r['count'] for r in rows]
        ax.pie(counts, labels=fault_types, autopct='%1.1f%%', startangle=90)
        ax.set_title('Page Fault Type Distribution', fontsize=13, fontweight='bold')
        
        # Average latency by type
        ax = axes[1]
        latencies = [r['avg_latency_us'] for r in rows]
        bars = ax.bar(fault_types, latencies, color='teal')
        ax.set_ylabel('Average Latency (μs)', fontsize=11)
        ax.set_xlabel('Fault Type', fontsize=11)
        ax.set_title('Average Page Fault Latency', fontsize=13, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, height,
                   f'{height:.1f}μs', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'pagefault_metrics.png', dpi=150)
        plt.close()
        logger.info("Page fault metrics plot saved")
    
    def plot_correlation_heatmap(self):
        """Plot correlation heatmap of aggregated metrics."""
        logger.info("Generating correlation heatmap...")
        
        # Aggregate key metrics by timestamp
        query = """
        SELECT 
            m.timestamp,
            m.mem_available_kb,
            m.cached_kb,
            m.dirty_kb,
            l.load_1min,
            l.running_processes,
            COALESCE(n.rx_bytes, 0) as rx_bytes,
            COALESCE(n.tx_bytes, 0) as tx_bytes,
            COALESCE(t.established, 0) as tcp_established,
            COALESCE(t.time_wait, 0) as tcp_time_wait
        FROM memory_metrics m
        LEFT JOIN load_metrics l ON m.timestamp = l.timestamp
        LEFT JOIN (
            SELECT timestamp, SUM(rx_bytes) as rx_bytes, SUM(tx_bytes) as tx_bytes
            FROM network_interface_stats
            GROUP BY timestamp
        ) n ON m.timestamp = n.timestamp
        LEFT JOIN tcp_stats t ON m.timestamp = t.timestamp
        ORDER BY m.timestamp
        """
        
        rows = self.db.query(query)
        if len(rows) < 2:
            logger.warning("Insufficient data for correlation analysis")
            return
        
        # Convert to numpy arrays
        data = {}
        for key in rows[0].keys():
            if key != 'timestamp':
                data[key] = np.array([r[key] if r[key] is not None else 0 for r in rows])
        
        # Create correlation matrix
        import pandas as pd
        df = pd.DataFrame(data)
        corr = df.corr()
        
        # Plot heatmap
        fig, ax = plt.subplots(figsize=(12, 10))
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', 
                   center=0, square=True, linewidths=1, ax=ax,
                   cbar_kws={'label': 'Correlation Coefficient'})
        ax.set_title('Metric Correlation Heatmap', fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'correlation_heatmap.png', dpi=150)
        plt.close()
        logger.info("Correlation heatmap saved")
    
    def plot_distributions(self):
        """Plot value distributions for key metrics."""
        logger.info("Generating distribution plots...")
        
        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(3, 3, figure=fig)
        
        # Memory available distribution
        ax = fig.add_subplot(gs[0, 0])
        data = self.db.query("SELECT mem_available_kb FROM memory_metrics")
        if data:
            values = [r['mem_available_kb']/1024/1024 for r in data]
            ax.hist(values, bins=30, color='skyblue', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Memory Available (GB)')
            ax.set_ylabel('Frequency')
            ax.set_title('Memory Available Distribution')
            ax.grid(alpha=0.3)
        
        # Load average distribution
        ax = fig.add_subplot(gs[0, 1])
        data = self.db.query("SELECT load_1min FROM load_metrics")
        if data:
            values = [r['load_1min'] for r in data]
            ax.hist(values, bins=30, color='lightcoral', edgecolor='black', alpha=0.7)
            ax.set_xlabel('1-min Load Average')
            ax.set_ylabel('Frequency')
            ax.set_title('Load Average Distribution')
            ax.grid(alpha=0.3)
        
        # Syscall latency distribution
        ax = fig.add_subplot(gs[0, 2])
        data = self.db.query("SELECT latency_ns FROM syscall_events WHERE latency_ns < 1000000000")
        if data:
            values = [r['latency_ns']/1000000.0 for r in data]  # Convert to ms
            ax.hist(values, bins=50, color='lightgreen', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Syscall Latency (ms)')
            ax.set_ylabel('Frequency')
            ax.set_title('Syscall Latency Distribution')
            ax.set_yscale('log')
            ax.grid(alpha=0.3)
        
        # TCP ESTABLISHED count distribution
        ax = fig.add_subplot(gs[1, 0])
        data = self.db.query("SELECT established FROM tcp_stats")
        if data:
            values = [r['established'] for r in data]
            ax.hist(values, bins=30, color='plum', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Established Connections')
            ax.set_ylabel('Frequency')
            ax.set_title('TCP ESTABLISHED Distribution')
            ax.grid(alpha=0.3)
        
        # Page fault latency distribution
        ax = fig.add_subplot(gs[1, 1])
        data = self.db.query("SELECT latency_ns FROM page_fault_events")
        if data:
            values = [r['latency_ns']/1000.0 for r in data]  # Convert to μs
            ax.hist(values, bins=50, color='gold', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Page Fault Latency (μs)')
            ax.set_ylabel('Frequency')
            ax.set_title('Page Fault Latency Distribution')
            ax.set_yscale('log')
            ax.grid(alpha=0.3)
        
        # Process count distribution
        ax = fig.add_subplot(gs[1, 2])
        data = self.db.query("SELECT total_processes FROM load_metrics")
        if data:
            values = [r['total_processes'] for r in data]
            ax.hist(values, bins=30, color='salmon', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Total Processes')
            ax.set_ylabel('Frequency')
            ax.set_title('Process Count Distribution')
            ax.grid(alpha=0.3)
        
        plt.suptitle('Metric Distributions', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'distributions.png', dpi=150)
        plt.close()
        logger.info("Distribution plots saved")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Comprehensive exploratory data analysis for KernelSight AI'
    )
    parser.add_argument(
        '--database', '-d',
        default='data/stress_test.db',
        help='Path to database file (default: data/stress_test.db)'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='data/reports/week1_integration',
        help='Output directory for reports and plots'
    )
    parser.add_argument(
        '--log-dir', '-l',
        default='logs/stress_test',
        help='Directory containing log files'
    )
    
    args = parser.parse_args()
    
    # Convert paths
    db_path = Path(args.database)
    output_dir = Path(args.output_dir)
    log_dir = Path(args.log_dir)
    
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.info("Please run a stress test first to generate data.")
        sys.exit(1)
    
    print("=" * 70)
    print("KernelSight AI - Week 1 Integration: Exploratory Data Analysis")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    print(f"Output:   {output_dir}")
    print(f"Logs:     {log_dir}\n")
    
    # Analyze database
    print("[1/2] Analyzing database and generating visualizations...")
    explorer = DataExplorer(str(db_path), output_dir)
    explorer.generate_all_reports()
    
    # Analyze logs
    print("\n[2/2] Analyzing log files...")
    log_analyzer = LogAnalyzer(log_dir)
    log_results = log_analyzer.analyze_all()
    
    # Save log analysis report
    log_report_path = output_dir / 'log_analysis.txt'
    with open(log_report_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("Log Analysis Report\n")
        f.write("=" * 70 + "\n\n")
        
        for log_type, results in log_results.items():
            if not results:
                continue
            
            f.write(f"\n{log_type.upper()} LOG:\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total lines: {results.get('total_lines', 0)}\n")
            
            if 'errors' in results and results['errors']:
                f.write(f"Errors: {len(results['errors'])}\n")
                for err in results['errors'][:5]:  # Show first 5
                    f.write(f"  - {err}\n")
            
            if 'warnings' in results and results['warnings']:
                f.write(f"Warnings: {len(results['warnings'])}\n")
            
            # Type-specific info
            if log_type == 'ingestion':
                f.write(f"Batches processed: {results.get('batches_processed', 0)}\n")
                f.write(f"Event types: {dict(results.get('event_types', {}))}\n")
            elif log_type == 'scraper':
                f.write(f"Collection cycles: {results.get('collection_cycles', 0)}\n")
                f.write(f"Collectors run: {results.get('collectors_run', [])}\n")
            elif 'ebpf' in log_type or log_type in ['syscall', 'io', 'pagefault', 'sched']:
                f.write(f"Initialization success: {results.get('initialization_success', False)}\n")
                f.write(f"Events emitted: {results.get('events_emitted', 0)}\n")
    
    logger.info(f"Log analysis report saved to {log_report_path}")
    
    # Clean up
    explorer.db.close()
    
    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)
    print(f"\nGenerated reports in: {output_dir.absolute()}")
    print("\nVisualizations created:")
    print("  - database_overview.txt")
    print("  - event_distribution.png")
    print("  - memory_metrics.png")
    print("  - load_metrics.png")
    print("  - network_*.png")
    print("  - tcp_metrics.png")
    print("  - io_metrics.png")
    print("  - syscall_metrics.png")
    print("  - pagefault_metrics.png")
    print("  - correlation_heatmap.png")
    print("  - distributions.png")
    print("  - log_analysis.txt")
    print()


if __name__ == '__main__':
    main()

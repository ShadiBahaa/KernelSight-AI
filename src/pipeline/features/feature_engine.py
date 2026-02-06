#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Feature engineering engine for KernelSight AI.

Supports dual modes:
- Batch: Process historical data from database for ML training
- Real-time: Incremental computation for live agent monitoring
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_manager import DatabaseManager
from query_utils import get_timestamp_ns
from .feature_definitions import FEATURE_CATALOG, get_base_features, get_derived_features

logger = logging.getLogger(__name__)


class RollingWindow:
    """Maintains a rolling window of values for incremental computation."""
    
    def __init__(self, window_size: int):
        """
        Initialize rolling window.
        
        Args:
            window_size: Maximum number of samples to keep
        """
        self.window_size = window_size
        self.values = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)
    
    def add(self, value: float, timestamp: int):
        """Add a value to the window."""
        self.values.append(value)
        self.timestamps.append(timestamp)
    
    def mean(self) -> Optional[float]:
        """Calculate mean of values in window."""
        if not self.values:
            return None
        return np.mean(self.values)
    
    def std(self) -> Optional[float]:
        """Calculate standard deviation of values in window."""
        if len(self.values) < 2:
            return None
        return np.std(self.values, ddof=1)
    
    def median(self) -> Optional[float]:
        """Calculate median of values in window."""
        if not self.values:
            return None
        return np.median(self.values)
    
    def get_latest(self) -> Optional[float]:
        """Get most recent value."""
        if not self.values:
            return None
        return self.values[-1]
    
    def get_delta(self) -> Optional[float]:
        """Get difference between latest and previous value."""
        if len(self.values) < 2:
            return None
        return self.values[-1] - self.values[-2]
    
    def get_rate(self) -> Optional[float]:
        """Get rate of change (delta / time_delta)."""
        if len(self.values) < 2:
            return None
        delta_value = self.values[-1] - self.values[-2]
        # Timestamps are in nanoseconds
        delta_time_sec = (self.timestamps[-1] - self.timestamps[-2]) / 1e9
        if delta_time_sec == 0:
            return None
        return delta_value / delta_time_sec


class FeatureEngine:
    """
    Feature computation engine supporting batch and real-time modes.
    """
    
    def __init__(
        self,
        mode: str = 'batch',
        db_path: Optional[str] = None,
        window_size: int = 60
    ):
        """
        Initialize feature engine.
        
        Args:
            mode: 'batch' or 'realtime'
            db_path: Path to database
            window_size: Default window size for rolling computations (seconds)
        """
        self.mode = mode
        self.db_path = db_path or 'data/kernelsight.db'
        self.window_size = window_size
        
        # For real-time mode: maintain rolling windows
        self.rolling_windows: Dict[str, RollingWindow] = {}
        
        # Baseline statistics (learned from batch mode, used in real-time)
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
        
        # Database connection
        self.db: Optional[DatabaseManager] = None
        if self.mode == 'batch':
            self.db = DatabaseManager(self.db_path)
        
        logger.info(f"FeatureEngine initialized in {mode} mode")
    
    def batch_compute(
        self,
        start_time: datetime,
        end_time: datetime,
        device: str = 'sda',
        interface: str = 'eth0'
    ) -> Dict[str, np.ndarray]:
        """
        Compute features over historical data (batch mode).
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            device: Block device name for I/O metrics
            interface: Network interface for network metrics
            
        Returns:
            Dictionary mapping feature names to numpy arrays
        """
        if self.mode != 'batch':
            raise ValueError("batch_compute only available in batch mode")
        
        logger.info(f"Computing features from {start_time} to {end_time}")
        
        # Fetch raw data from database
        raw_data = self._fetch_batch_data(start_time, end_time, device, interface)
        
        # Compute features
        features = self._compute_batch_features(raw_data)
        
        # Compute baseline statistics for z-scores
        self._compute_baseline_stats(features)
        
        # Add z-score features
        features.update(self._compute_zscore_features(features))
        
        return features
    
    def _fetch_batch_data(
        self,
        start_time: datetime,
        end_time: datetime,
        device: str,
        interface: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch raw telemetry data from database."""
        start_ns = get_timestamp_ns(start_time)
        end_ns = get_timestamp_ns(end_time)
        
        data = {}
        
        # Memory metrics
        sql = """
            SELECT timestamp, mem_total_kb, mem_available_kb, mem_free_kb,
                   buffers_kb, cached_kb, swap_total_kb, swap_free_kb,
                   dirty_kb, writeback_kb
            FROM memory_metrics
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (start_ns, end_ns))
        data['memory'] = [dict(row) for row in rows]
        
        # Block stats
        sql = """
            SELECT timestamp, read_ios, write_ios, read_sectors, write_sectors,
                   read_ticks, write_ticks, in_flight
            FROM block_stats
            WHERE device_name = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (device, start_ns, end_ns))
        data['block'] = [dict(row) for row in rows]
        
        # Network stats
        sql = """
            SELECT timestamp, rx_bytes, tx_bytes, rx_packets, tx_packets,
                   rx_errors, tx_errors, rx_drops, tx_drops
            FROM network_interface_stats
            WHERE interface_name = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (interface, start_ns, end_ns))
        data['network'] = [dict(row) for row in rows]
        
        # TCP stats
        sql = """
            SELECT timestamp, established, syn_sent, syn_recv, time_wait,
                   listen, close_wait
            FROM tcp_stats
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (start_ns, end_ns))
        data['tcp'] = [dict(row) for row in rows]
        
        # TCP retransmits
        sql = """
            SELECT timestamp, retrans_segs
            FROM tcp_retransmit_stats
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (start_ns, end_ns))
        data['tcp_retrans'] = [dict(row) for row in rows]
        
        # Load metrics
        sql = """
            SELECT timestamp, load_1min, load_5min, load_15min
            FROM load_metrics
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (start_ns, end_ns))
        data['load'] = [dict(row) for row in rows]
        
        # I/O latency stats
        sql = """
            SELECT timestamp, read_p95_us, write_p95_us, read_p99_us, write_p99_us
            FROM io_latency_stats
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp
        """
        rows = self.db.query(sql, (start_ns, end_ns))
        data['io_latency'] = [dict(row) for row in rows]
        
        logger.info(f"Fetched {len(data['memory'])} memory, {len(data['block'])} block, "
                   f"{len(data['network'])} network samples")
        
        return data
    
    def _compute_batch_features(self, raw_data: Dict[str, List[Dict]]) -> Dict[str, np.ndarray]:
        """Compute features from raw data."""
        features = {}
        
        # Extract timestamps (use memory as reference)
        if not raw_data['memory']:
            logger.warning("No memory data available")
            return features
        
        timestamps = np.array([row['timestamp'] for row in raw_data['memory']])
        features['timestamp'] = timestamps

        
        # ===== Memory Features =====
        if raw_data['memory']:
            mem_data = raw_data['memory']
            features['mem_available_mb'] = np.array([
                row['mem_available_kb'] / 1024.0 if row['mem_available_kb'] is not None else np.nan
                for row in mem_data
            ])
            
            mem_total = np.array([row['mem_total_kb'] for row in mem_data])
            mem_avail = features['mem_available_mb'] * 1024
            features['mem_used_pct'] = (mem_total - mem_avail) / mem_total * 100
            
            # Rolling average (5-minute window)
            features['mem_available_rolling_avg'] = self._rolling_mean(
                features['mem_available_mb'], window=300
            )
            
            # Memory pressure
            swap_total = np.array([row.get('swap_total_kb', 0) or 0 for row in mem_data])
            swap_free = np.array([row.get('swap_free_kb', 0) or 0 for row in mem_data])
            dirty = np.array([row.get('dirty_kb', 0) or 0 for row in mem_data])
            writeback = np.array([row.get('writeback_kb', 0) or 0 for row in mem_data])
            features['mem_pressure'] = (swap_total - swap_free + dirty + writeback) / 1024.0
            
            # Memory availability rate
            features['mem_available_rate'] = self._compute_rate(
                features['mem_available_mb'], timestamps
            )
        
        # ===== I/O Features =====
        if raw_data['block']:
            block_data = raw_data['block']
            
            # Extract sectors
            read_sectors = np.array([row.get('read_sectors', 0) or 0 for row in block_data])
            write_sectors = np.array([row.get('write_sectors', 0) or 0 for row in block_data])
            
            # Compute throughput (MB/s)
            block_timestamps = np.array([row['timestamp'] for row in block_data])
            features['io_read_throughput_mbps'] = self._compute_rate(
                read_sectors * 512 / 1024 / 1024, block_timestamps
            )
            features['io_write_throughput_mbps'] = self._compute_rate(
                write_sectors * 512 / 1024 / 1024, block_timestamps
            )
            
            # Queue depth
            features['io_queue_depth'] = np.array([
                row.get('in_flight', 0) or 0 for row in block_data
            ])
            
            # I/O ops per second
            read_ios = np.array([row.get('read_ios', 0) or 0 for row in block_data])
            write_ios = np.array([row.get('write_ios', 0) or 0 for row in block_data])
            features['io_ops_per_sec'] = self._compute_rate(
                read_ios + write_ios, block_timestamps
            )
        
        # I/O Latency
        if raw_data['io_latency']:
            io_lat_data = raw_data['io_latency']
            features['io_latency_read_p95'] = np.array([
                row.get('read_p95_us') or np.nan for row in io_lat_data
            ])
            features['io_latency_write_p95'] = np.array([
                row.get('write_p95_us') or np.nan for row in io_lat_data
            ])
        
        # ===== Network Features =====
        if raw_data['network']:
            net_data = raw_data['network']
            net_timestamps = np.array([row['timestamp'] for row in net_data])
            
            rx_bytes = np.array([row.get('rx_bytes', 0) or 0 for row in net_data])
            tx_bytes = np.array([row.get('tx_bytes', 0) or 0 for row in net_data])
            
            features['net_rx_throughput_mbps'] = self._compute_rate(
                rx_bytes / 1024 / 1024, net_timestamps
            )
            features['net_tx_throughput_mbps'] = self._compute_rate(
                tx_bytes / 1024 / 1024, net_timestamps
            )
            
            # Error rates
            rx_errors = np.array([row.get('rx_errors', 0) or 0 for row in net_data])
            tx_errors = np.array([row.get('tx_errors', 0) or 0 for row in net_data])
            features['net_error_rate'] = self._compute_rate(
                rx_errors + tx_errors, net_timestamps
            )
            
            rx_drops = np.array([row.get('rx_drops', 0) or 0 for row in net_data])
            tx_drops = np.array([row.get('tx_drops', 0) or 0 for row in net_data])
            features['net_drop_rate'] = self._compute_rate(
                rx_drops + tx_drops, net_timestamps
            )
        
        # TCP features
        if raw_data['tcp']:
            tcp_data = raw_data['tcp']
            tcp_timestamps = np.array([row['timestamp'] for row in tcp_data])
            
            established = np.array([row.get('established', 0) or 0 for row in tcp_data])
            features['tcp_connection_rate'] = self._compute_rate(established, tcp_timestamps)
        
        if raw_data['tcp_retrans']:
            tcp_retrans_data = raw_data['tcp_retrans']
            tcp_retrans_timestamps = np.array([row['timestamp'] for row in tcp_retrans_data])
            
            retrans_segs = np.array([row.get('retrans_segs', 0) or 0 for row in tcp_retrans_data])
            features['tcp_retransmit_rate'] = self._compute_rate(retrans_segs, tcp_retrans_timestamps)
        
        # ===== System Load Features =====
        if raw_data['load']:
            load_data = raw_data['load']
            features['load_1min'] = np.array([row.get('load_1min') or np.nan for row in load_data])
            features['load_5min'] = np.array([row.get('load_5min') or np.nan for row in load_data])
            features['load_trend'] = features['load_1min'] - features['load_5min']
        
        logger.info(f"Computed {len(features)} base features")
        return features
    
    def _rolling_mean(self, values: np.ndarray, window: int) -> np.ndarray:
        """Compute rolling mean with specified window size (in samples)."""
        result = np.full_like(values, np.nan)
        for i in range(len(values)):
            start_idx = max(0, i - window + 1)
            result[i] = np.nanmean(values[start_idx:i+1])
        return result
    
    def _compute_rate(self, values: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
        """Compute rate of change (delta / delta_time)."""
        if len(values) < 2:
            return np.array([])
        
        delta_values = np.diff(values)
        delta_times = np.diff(timestamps) / 1e9  # Convert ns to seconds
        
        # Avoid division by zero
        rates = np.where(delta_times > 0, delta_values / delta_times, 0)
        
        # Prepend NaN to match original length
        return np.concatenate([[np.nan], rates])
    
    def _compute_baseline_stats(self, features: Dict[str, np.ndarray]):
        """Compute baseline statistics for anomaly detection."""
        for feature_name, values in features.items():
            if feature_name == 'timestamp':
                continue
            
            # Filter out NaN and Inf
            valid_values = values[np.isfinite(values)]
            
            if len(valid_values) > 0:
                self.baseline_stats[feature_name] = {
                    'mean': float(np.mean(valid_values)),
                    'std': float(np.std(valid_values, ddof=1)) if len(valid_values) > 1 else 0.0,
                    'min': float(np.min(valid_values)),
                    'max': float(np.max(valid_values))
                }
        
        logger.info(f"Computed baseline statistics for {len(self.baseline_stats)} features")
    
    def _compute_zscore_features(self, features: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Compute z-score features for anomaly detection."""
        zscore_features = {}
        
        # Define which features to compute z-scores for
        zscore_targets = {
            'mem_used_pct': 'mem_used_pct_zscore',
            'io_latency_write_p95': 'io_latency_p95_zscore',
            'net_rx_throughput_mbps': 'net_throughput_zscore',  # Simplified: just RX for now
        }
        
        for base_feature, zscore_name in zscore_targets.items():
            if base_feature in features and base_feature in self.baseline_stats:
                values = features[base_feature]
                stats = self.baseline_stats[base_feature]
                
                if stats['std'] > 0:
                    zscore_features[zscore_name] = (values - stats['mean']) / stats['std']
                else:
                    zscore_features[zscore_name] = np.zeros_like(values)
        
        return zscore_features
    
    def get_baseline_stats(self) -> Dict[str, Dict[str, float]]:
        """Get computed baseline statistics."""
        return self.baseline_stats
    
    def save_baseline_stats(self, filepath: str):
        """Save baseline statistics to JSON file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.baseline_stats, f, indent=2)
        logger.info(f"Saved baseline statistics to {filepath}")
    
    def load_baseline_stats(self, filepath: str):
        """Load baseline statistics from JSON file."""
        import json
        with open(filepath, 'r') as f:
            self.baseline_stats = json.load(f)
        logger.info(f"Loaded baseline statistics from {filepath}")
    
    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()

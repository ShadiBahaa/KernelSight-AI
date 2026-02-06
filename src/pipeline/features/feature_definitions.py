#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Feature definitions catalog for KernelSight AI.

This module defines all available features, their computation methods,
metadata, and default parameters.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class FeatureGroup(Enum):
    """Feature groups for organization."""
    MEMORY = "memory"
    IO = "io"
    NETWORK = "network"
    CPU = "cpu"
    SYSTEM_LOAD = "system_load"
    DERIVED = "derived"


@dataclass
class FeatureDefinition:
    """Definition of a single feature."""
    name: str
    group: FeatureGroup
    description: str
    formula: str
    unit: Optional[str] = None
    default_window_size: int = 60  # seconds
    interpretation: Optional[str] = None
    suggested_threshold: Optional[float] = None
    related_subsystems: List[str] = None
    
    def __post_init__(self):
        if self.related_subsystems is None:
            self.related_subsystems = []


# Feature Catalog
FEATURE_CATALOG: Dict[str, FeatureDefinition] = {
    
    # ========== Memory Features ==========
    "mem_available_mb": FeatureDefinition(
        name="mem_available_mb",
        group=FeatureGroup.MEMORY,
        description="Available memory in megabytes",
        formula="mem_available_kb / 1024",
        unit="MB",
        interpretation="Memory available for new applications without swapping",
        related_subsystems=["memory_manager", "page_allocator"]
    ),
    
    "mem_used_pct": FeatureDefinition(
        name="mem_used_pct",
        group=FeatureGroup.MEMORY,
        description="Memory usage percentage",
        formula="(mem_total - mem_available) / mem_total * 100",
        unit="%",
        interpretation="Percentage of total memory in use",
        suggested_threshold=85.0,
        related_subsystems=["memory_manager"]
    ),
    
    "mem_available_rolling_avg": FeatureDefinition(
        name="mem_available_rolling_avg",
        group=FeatureGroup.MEMORY,
        description="Rolling average of available memory",
        formula="rolling_mean(mem_available_mb, window)",
        unit="MB",
        default_window_size=300,  # 5 minutes
        interpretation="Smoothed memory availability trend",
        related_subsystems=["memory_manager"]
    ),
    
    "mem_pressure": FeatureDefinition(
        name="mem_pressure",
        group=FeatureGroup.MEMORY,
        description="Memory pressure indicator",
        formula="swap_used_mb + dirty_mb + writeback_mb",
        unit="MB",
        interpretation="High values indicate memory contention",
        suggested_threshold=500.0,
        related_subsystems=["swap", "page_writeback"]
    ),
    
    "mem_available_rate": FeatureDefinition(
        name="mem_available_rate",
        group=FeatureGroup.MEMORY,
        description="Rate of change in available memory",
        formula="delta(mem_available_mb) / delta_time_sec",
        unit="MB/s",
        interpretation="Negative = memory consumption, Positive = memory release",
        related_subsystems=["memory_manager"]
    ),
    
    # ========== I/O Features ==========
    "io_read_throughput_mbps": FeatureDefinition(
        name="io_read_throughput_mbps",
        group=FeatureGroup.IO,
        description="Read throughput in MB per second",
        formula="delta(read_sectors * 512) / delta_time_sec / 1024 / 1024",
        unit="MB/s",
        interpretation="Block device read bandwidth",
        related_subsystems=["block_layer", "io_scheduler"]
    ),
    
    "io_write_throughput_mbps": FeatureDefinition(
        name="io_write_throughput_mbps",
        group=FeatureGroup.IO,
        description="Write throughput in MB per second",
        formula="delta(write_sectors * 512) / delta_time_sec / 1024 / 1024",
        unit="MB/s",
        interpretation="Block device write bandwidth",
        related_subsystems=["block_layer", "io_scheduler"]
    ),
    
    "io_latency_read_p95": FeatureDefinition(
        name="io_latency_read_p95",
        group=FeatureGroup.IO,
        description="95th percentile read latency",
        formula="read_p95_us",
        unit="μs",
        interpretation="High values indicate slow storage",
        suggested_threshold=10000.0,  # 10ms
        related_subsystems=["block_layer", "storage_driver"]
    ),
    
    "io_latency_write_p95": FeatureDefinition(
        name="io_latency_write_p95",
        group=FeatureGroup.IO,
        description="95th percentile write latency",
        formula="write_p95_us",
        unit="μs",
        interpretation="High values indicate slow storage",
        suggested_threshold=10000.0,
        related_subsystems=["block_layer", "storage_driver"]
    ),
    
    "io_queue_depth": FeatureDefinition(
        name="io_queue_depth",
        group=FeatureGroup.IO,
        description="Number of I/O operations in flight",
        formula="in_flight",
        unit="requests",
        interpretation="High values indicate I/O congestion",
        suggested_threshold=32.0,
        related_subsystems=["io_scheduler", "block_layer"]
    ),
    
    "io_ops_per_sec": FeatureDefinition(
        name="io_ops_per_sec",
        group=FeatureGroup.IO,
        description="Total I/O operations per second",
        formula="delta(read_ios + write_ios) / delta_time_sec",
        unit="ops/s",
        interpretation="I/O workload intensity",
        related_subsystems=["block_layer"]
    ),
    
    # ========== Network Features ==========
    "net_rx_throughput_mbps": FeatureDefinition(
        name="net_rx_throughput_mbps",
        group=FeatureGroup.NETWORK,
        description="Network receive throughput",
        formula="delta(rx_bytes) / delta_time_sec / 1024 / 1024",
        unit="MB/s",
        interpretation="Network ingress bandwidth",
        related_subsystems=["network_stack", "interface"]
    ),
    
    "net_tx_throughput_mbps": FeatureDefinition(
        name="net_tx_throughput_mbps",
        group=FeatureGroup.NETWORK,
        description="Network transmit throughput",
        formula="delta(tx_bytes) / delta_time_sec / 1024 / 1024",
        unit="MB/s",
        interpretation="Network egress bandwidth",
        related_subsystems=["network_stack", "interface"]
    ),
    
    "net_error_rate": FeatureDefinition(
        name="net_error_rate",
        group=FeatureGroup.NETWORK,
        description="Network error rate",
        formula="delta(rx_errors + tx_errors) / delta_time_sec",
        unit="errors/s",
        interpretation="Network reliability indicator",
        suggested_threshold=1.0,
        related_subsystems=["network_stack", "network_driver"]
    ),
    
    "net_drop_rate": FeatureDefinition(
        name="net_drop_rate",
        group=FeatureGroup.NETWORK,
        description="Packet drop rate",
        formula="delta(rx_drops + tx_drops) / delta_time_sec",
        unit="drops/s",
        interpretation="Indicates buffer overflow or congestion",
        suggested_threshold=10.0,
        related_subsystems=["network_stack", "network_buffer"]
    ),
    
    "tcp_connection_rate": FeatureDefinition(
        name="tcp_connection_rate",
        group=FeatureGroup.NETWORK,
        description="TCP new connection rate",
        formula="delta(established) / delta_time_sec",
        unit="conn/s",
        interpretation="Application connection activity",
        related_subsystems=["tcp_stack"]
    ),
    
    "tcp_retransmit_rate": FeatureDefinition(
        name="tcp_retransmit_rate",
        group=FeatureGroup.NETWORK,
        description="TCP retransmission rate",
        formula="delta(retrans_segs) / delta_time_sec",
        unit="segs/s",
        interpretation="Network congestion or packet loss indicator",
        suggested_threshold=100.0,
        related_subsystems=["tcp_stack", "network_congestion"]
    ),
    
    # ========== System Load Features ==========
    "load_1min": FeatureDefinition(
        name="load_1min",
        group=FeatureGroup.SYSTEM_LOAD,
        description="1-minute load average",
        formula="load_1min",
        unit="load",
        interpretation="Number of processes waiting for CPU",
        related_subsystems=["scheduler"]
    ),
    
    "load_5min": FeatureDefinition(
        name="load_5min",
        group=FeatureGroup.SYSTEM_LOAD,
        description="5-minute load average",
        formula="load_5min",
        unit="load",
        interpretation="Medium-term CPU demand",
        related_subsystems=["scheduler"]
    ),
    
    "load_trend": FeatureDefinition(
        name="load_trend",
        group=FeatureGroup.SYSTEM_LOAD,
        description="Load trend indicator",
        formula="load_1min - load_5min",
        unit="load",
        interpretation="Positive = increasing load, Negative = decreasing",
        related_subsystems=["scheduler"]
    ),
    
    # ========== Z-Score Features (for anomaly detection) ==========
    "mem_used_pct_zscore": FeatureDefinition(
        name="mem_used_pct_zscore",
        group=FeatureGroup.DERIVED,
        description="Z-score of memory usage percentage",
        formula="(mem_used_pct - mean) / std",
        unit="σ",
        interpretation="Standard deviations from baseline",
        suggested_threshold=3.0,
        related_subsystems=["memory_manager"]
    ),
    
    "io_latency_p95_zscore": FeatureDefinition(
        name="io_latency_p95_zscore",
        group=FeatureGroup.DERIVED,
        description="Z-score of I/O latency p95",
        formula="(io_latency_write_p95 - mean) / std",
        unit="σ",
        interpretation="Detects abnormal storage performance",
        suggested_threshold=3.0,
        related_subsystems=["block_layer", "storage_driver"]
    ),
    
    "net_throughput_zscore": FeatureDefinition(
        name="net_throughput_zscore",
        group=FeatureGroup.DERIVED,
        description="Z-score of network throughput",
        formula="(net_rx_throughput_mbps + net_tx_throughput_mbps - mean) / std",
        unit="σ",
        interpretation="Detects unusual network activity",
        suggested_threshold=3.0,
        related_subsystems=["network_stack"]
    ),
}


def get_features_by_group(group: FeatureGroup) -> Dict[str, FeatureDefinition]:
    """Get all features in a specific group."""
    return {
        name: feature 
        for name, feature in FEATURE_CATALOG.items() 
        if feature.group == group
    }


def get_feature_names() -> List[str]:
    """Get list of all feature names."""
    return list(FEATURE_CATALOG.keys())


def get_base_features() -> List[str]:
    """Get non-derived (base) feature names."""
    return [
        name for name, feature in FEATURE_CATALOG.items()
        if feature.group != FeatureGroup.DERIVED
    ]


def get_derived_features() -> List[str]:
    """Get derived feature names (z-scores, etc)."""
    return [
        name for name, feature in FEATURE_CATALOG.items()
        if feature.group == FeatureGroup.DERIVED
    ]

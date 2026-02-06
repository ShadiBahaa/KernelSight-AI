#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
System Metrics Semantic Classifier

Transforms raw system metrics into pressure indicators and semantic observations for Gemini 3.
Calculates memory pressure, I/O congestion, load mismatch, network health, etc.
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class PressureType(Enum):
    """Types of system pressure."""
    MEMORY_PRESSURE = "memory_pressure"
    IO_CONGESTION = "io_congestion"
    LOAD_MISMATCH = "load_mismatch"
    NETWORK_DEGRADATION = "network_degradation"
    TCP_EXHAUSTION = "tcp_exhaustion"
    SWAP_THRASHING = "swap_thrashing"
    BLOCK_DEVICE_SATURATION = "block_device_saturation"
    NONE = "none"


class SeverityLevel(Enum):
    """Severity of the pressure."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PressurePattern:
    """Describes what a pressure pattern means for the agent."""
    pressure_type: PressureType
    description: str
    typical_causes: List[str]
    agent_interpretation: str
    reasoning_hints: List[str]


@dataclass
class SystemObservation:
    """Semantic observation from system metrics."""
    timestamp: int
    pressure_type: PressureType
    severity: SeverityLevel
    summary: str  # Natural language summary for Gemini
    patterns: List[str]  # Behavioral patterns detected
    reasoning_hints: List[str]  # Suggested investigation paths
    pressure_score: float  # 0.0-1.0 normalized pressure
    metrics: Dict[str, float]  # Raw metrics
    context: Dict[str, any] = field(default_factory=dict)


class SystemMetricsClassifier:
    """
    Classifies system metrics into pressure indicators and generates
    semantic observations for agent reasoning.
    """
    
    # ============================================================
    # TESTING THRESHOLDS - Set LOW for demo/testing purposes
    # TODO: Restore production thresholds before deployment
    # ============================================================
    
    # Memory pressure thresholds (percentage of memory unavailable)
    # PRODUCTION: LOW=0.7, MEDIUM=0.85, HIGH=0.95, CRITICAL=0.98
    MEMORY_PRESSURE_LOW = 0.10       # 10% used (TEST - was 70%)
    MEMORY_PRESSURE_MEDIUM = 0.20    # 20% used (TEST - was 85%)
    MEMORY_PRESSURE_HIGH = 0.40      # 40% used (TEST - was 95%)
    MEMORY_PRESSURE_CRITICAL = 0.60  # 60% used (TEST - was 98%)
    
    # I/O congestion thresholds (queue depth ratio)
    IO_QUEUE_LOW = 0.05       # 5% of max queue (TEST - was 30%)
    IO_QUEUE_MEDIUM = 0.15    # 15% of max queue (TEST - was 60%)
    IO_QUEUE_HIGH = 0.30      # 30% of max queue (TEST - was 80%)
    IO_QUEUE_CRITICAL = 0.50  # 50% of max queue (TEST - was 95%)
    
    # Load mismatch thresholds (load / num_cpus ratio)
    # PRODUCTION: NORMAL=1.0, HIGH=2.0, CRITICAL=4.0, EXTREME=8.0
    LOAD_NORMAL = 0.25      # 0.25× cores (TEST - was 1.0×)
    LOAD_HIGH = 0.50        # 0.5× cores (TEST - was 2.0×)
    LOAD_CRITICAL = 1.0     # 1× cores (TEST - was 4.0×)
    LOAD_EXTREME = 2.0      # 2× cores (TEST - was 8.0×)
    
    # Network error rate thresholds (percentage)
    NETWORK_ERROR_LOW = 0.001     # 0.001% errors (TEST - was 0.01%)
    NETWORK_ERROR_MEDIUM = 0.01   # 0.01% errors (TEST - was 0.1%)
    NETWORK_ERROR_HIGH = 0.1      # 0.1% errors (TEST - was 1%)
    NETWORK_ERROR_CRITICAL = 0.5  # 0.5% errors (TEST - was 5%)
    
    # TCP connection thresholds
    TCP_TIME_WAIT_HIGH = 50        # >50 TIME_WAIT (TEST - was 1000)
    TCP_TIME_WAIT_CRITICAL = 200   # >200 TIME_WAIT (TEST - was 5000)
    TCP_CLOSE_WAIT_HIGH = 10       # >10 CLOSE_WAIT (TEST - was 100)
    TCP_SYN_RECV_HIGH = 50         # >50 SYN_RECV (TEST - was 500)
    
    # Swap usage thresholds (percentage of swap used)
    SWAP_LOW = 0.01       # 1% swap used (TEST - was 10%)
    SWAP_MEDIUM = 0.10    # 10% swap used (TEST - was 50%)
    SWAP_HIGH = 0.30      # 30% swap used (TEST - was 80%)
    SWAP_CRITICAL = 0.50  # 50% swap used (TEST - was 95%)
    
    # Pattern descriptions
    PATTERNS = {
        PressureType.MEMORY_PRESSURE: PressurePattern(
            pressure_type=PressureType.MEMORY_PRESSURE,
            description="Memory availability declining",
            typical_causes=[
                "Memory leak in application",
                "Workload spike exceeding capacity",
                "Insufficient memory for workload",
                "Cache/buffer growth"
            ],
            agent_interpretation="Memory pressure: System running low on available memory",
            reasoning_hints=[
                "Identify processes with highest memory usage",
                "Check for recent memory growth trends",
                "Look for memory leaks (steadily increasing RSS)",
                "Correlate with deployment or workload changes"
            ]
        ),
        PressureType.IO_CONGESTION: PressurePattern(
            pressure_type=PressureType.IO_CONGESTION,
            description="I/O queue saturation",
            typical_causes=[
                "Slow or saturated storage device",
                "Excessive I/O operations",
                "Random access pattern overwhelming disk",
                "Network filesystem latency"
            ],
            agent_interpretation="I/O congestion: Storage subsystem saturated",
            reasoning_hints=[
                "Check disk queue depth and utilization",
                "Correlate with syscall I/O latency",
                "Identify processes with high I/O rate",
                "Look for random vs sequential access patterns"
            ]
        ),
        PressureType.LOAD_MISMATCH: PressurePattern(
            pressure_type=PressureType.LOAD_MISMATCH,
            description="Load average exceeding CPU capacity",
            typical_causes=[
                "CPU-bound workload",
                "Too many concurrent processes",
                "Processes blocked on I/O (high load, low CPU)",
                "Scheduler imbalance"
            ],
            agent_interpretation="Load mismatch: Demand exceeds CPU capacity",
            reasoning_hints=[
                "Check if load is CPU-bound or I/O-bound",
                "Count runnable vs blocked processes",
                "Correlate with scheduler events",
                "Identify top CPU consumers"
            ]
        ),
        PressureType.NETWORK_DEGRADATION: PressurePattern(
            pressure_type=PressureType.NETWORK_DEGRADATION,
            description="Network errors or packet loss",
            typical_causes=[
                "Bad network hardware (cable, NIC, switch)",
                "Network congestion",
                "MTU mismatch",
                "Driver or firmware issues"
            ],
            agent_interpretation="Network degradation: Packet errors or drops detected",
            reasoning_hints=[
                "Check physical network connectivity",
                "Monitor error types (RX vs TX)",
                "Correlate with network syscall latency",
                "Look for retransmit rates"
            ]
        ),
        PressureType.TCP_EXHAUSTION: PressurePattern(
            pressure_type=PressureType.TCP_EXHAUSTION,
            description="Excessive TCP connection states",
            typical_causes=[
                "Connection churning (not reusing connections)",
                "Application not closing connections (CLOSE_WAIT)",
                "SYN flood attack (SYN_RECV accumulation)",
                "Kernel parameter limits"
            ],
            agent_interpretation="TCP exhaustion: Connection state buildup",
            reasoning_hints=[
                "Check for connection pool misconfig",
                "Identify processes with most connections",
                "Look for TIME_WAIT accumulation (need SO_REUSEADDR)",
                "Monitor for SYN flood (firewall/rate limiting)"
            ]
        ),
        PressureType.SWAP_THRASHING: PressurePattern(
            pressure_type=PressureType.SWAP_THRASHING,
            description="Heavy swap usage and page faults",
            typical_causes=[
                "Working set exceeds physical memory",
                "Memory leak forcing pages to swap",
                "Insufficient RAM for workload",
                "NUMA imbalance"
            ],
            agent_interpretation="Swap thrashing: Pages constantly swapped in/out",
            reasoning_hints=[
                "Check major page fault rate",
                "Identify processes using swap",
                "Correlate with memory pressure",
                "Consider adding RAM or reducing workload"
            ]
        ),
        PressureType.BLOCK_DEVICE_SATURATION: PressurePattern(
            pressure_type=PressureType.BLOCK_DEVICE_SATURATION,
            description="Block device I/O saturation",
            typical_causes=[
                "Disk queue depth maxed out",
                "High IOPS workload",
                "Slow storage device",
                "Too many concurrent I/O operations"
            ],
            agent_interpretation="Block device saturation: Storage device overloaded",
            reasoning_hints=[
                "Check disk utilization percentage",
                "Monitor queue depth and wait times",
                "Identify processes with highest I/O",
                "Consider faster storage or I/O scheduling tuning"
            ]
        )
    }
    
    def __init__(self, num_cpus: int = 4, max_io_queue: int = 128):
        """
        Initialize classifier.
        
        Args:
            num_cpus: Number of CPU cores
            max_io_queue: Maximum I/O queue depth
        """
        self.num_cpus = num_cpus
        self.max_io_queue = max_io_queue
    
    def calculate_memory_pressure(self, metrics: Dict) -> float:
        """
        Calculate memory pressure score (0.0-1.0).
        
        Args:
            metrics: Dict with mem_total_kb, mem_available_kb
            
        Returns:
            Pressure score (0=no pressure, 1=critical)
        """
        total = metrics.get('mem_total_kb', 1)
        available = metrics.get('mem_available_kb', total)
        
        # Pressure = 1 - (available / total)
        pressure = 1.0 - (available / total)
        return max(0.0, min(1.0, pressure))
    
    def calculate_io_congestion(self, metrics: Dict) -> float:
        """
        Calculate I/O congestion score (0.0-1.0).
        
        Args:
            metrics: Dict with io_queue_depth (optional)
            
        Returns:
            Congestion score (0=no congestion, 1=saturated)
        """
        queue_depth = metrics.get('io_queue_depth', 0)
        
        # Congestion = queue_depth / max_queue
        congestion = queue_depth / self.max_io_queue
        return max(0.0, min(1.0, congestion))
    
    def calculate_load_mismatch(self, metrics: Dict) -> float:
        """
        Calculate load mismatch score (0.0-1.0).
        
        Args:
            metrics: Dict with load_1min
            
        Returns:
            Mismatch score (0=balanced, 1=severe overload)
        """
        load = metrics.get('load_1min', 0)
        
        # Mismatch = load / num_cpus, capped at 1.0 for 4× overload
        mismatch = load / (self.num_cpus * 4.0)
        return max(0.0, min(1.0, mismatch))
    
    def calculate_network_health(self, metrics: Dict) -> float:
        """
        Calculate network health score (0.0=healthy, 1.0=degraded).
        
        Args:
            metrics: Dict with rx_packets, rx_errors, tx_packets, tx_errors
            
        Returns:
            Degradation score
        """
        rx_packets = metrics.get('rx_packets', 0)
        rx_errors = metrics.get('rx_errors', 0)
        tx_packets = metrics.get('tx_packets', 0)
        tx_errors = metrics.get('tx_errors', 0)
        
        total_packets = rx_packets + tx_packets
        total_errors = rx_errors + tx_errors
        
        if total_packets == 0:
            return 0.0
        
        error_rate = (total_errors / total_packets) * 100  # Percentage
        
        # Map error rate to 0-1 score
        # 0.01% = low, 1% = medium, 5% = critical
        degradation = min(1.0, error_rate / 5.0)
        return degradation
    
    def classify_pressure(self, metrics: Dict) -> PressureType:
        """
        Classify primary pressure type from metrics.
        
        Args:
            metrics: System metrics dictionary
            
        Returns:
            Primary PressureType
        """
        # Calculate all pressure scores
        mem_pressure = self.calculate_memory_pressure(metrics)
        io_congestion = self.calculate_io_congestion(metrics)
        load_mismatch = self.calculate_load_mismatch(metrics)
        net_degradation = self.calculate_network_health(metrics)
        
        # Check swap thrashing
        swap_used = metrics.get('swap_used_kb', 0)
        swap_total = metrics.get('swap_total_kb', 1)
        swap_usage = swap_used / swap_total if swap_total > 0 else 0
        
        # Check TCP states
        time_wait = metrics.get('tcp_time_wait', 0)
        close_wait = metrics.get('tcp_close_wait', 0)
        syn_recv = metrics.get('tcp_syn_recv', 0)
        
        # Prioritize by severity
        if swap_usage > self.SWAP_LOW:
            return PressureType.SWAP_THRASHING
        
        if mem_pressure > self.MEMORY_PRESSURE_LOW:
            return PressureType.MEMORY_PRESSURE
        
        if (time_wait > self.TCP_TIME_WAIT_HIGH or 
            close_wait > self.TCP_CLOSE_WAIT_HIGH or
            syn_recv > self.TCP_SYN_RECV_HIGH):
            return PressureType.TCP_EXHAUSTION
        
        if io_congestion > self.IO_QUEUE_LOW:
            return PressureType.IO_CONGESTION
        
        if load_mismatch > self.LOAD_NORMAL:  # 0.25× cores (TEST - was 0.5)
            return PressureType.LOAD_MISMATCH
        
        if net_degradation > self.NETWORK_ERROR_LOW:  # 0.001% error rate (TEST - was 0.2)
            return PressureType.NETWORK_DEGRADATION
        
        return PressureType.NONE
    
    def assess_severity(self, pressure_type: PressureType, pressure_score: float, 
                       metrics: Dict) -> SeverityLevel:
        """
        Determine severity based on pressure type and score.
        
        Args:
            pressure_type: Type of pressure
            pressure_score: Normalized pressure score (0-1)
            metrics: Raw metrics
            
        Returns:
            SeverityLevel
        """
        if pressure_type == PressureType.NONE:
            return SeverityLevel.NONE
        
        if pressure_type == PressureType.MEMORY_PRESSURE:
            if pressure_score >= self.MEMORY_PRESSURE_CRITICAL:
                return SeverityLevel.CRITICAL
            elif pressure_score >= self.MEMORY_PRESSURE_HIGH:
                return SeverityLevel.HIGH
            elif pressure_score >= self.MEMORY_PRESSURE_MEDIUM:
                return SeverityLevel.MEDIUM
            else:
                return SeverityLevel.LOW
        
        if pressure_type == PressureType.IO_CONGESTION:
            if pressure_score >= self.IO_QUEUE_CRITICAL:
                return SeverityLevel.CRITICAL
            elif pressure_score >= self.IO_QUEUE_HIGH:
                return SeverityLevel.HIGH
            elif pressure_score >= self.IO_QUEUE_MEDIUM:
                return SeverityLevel.MEDIUM
            else:
                return SeverityLevel.LOW
        
        if pressure_type == PressureType.LOAD_MISMATCH:
            load_ratio = metrics.get('load_1min', 0) / self.num_cpus
            if load_ratio >= self.LOAD_EXTREME:
                return SeverityLevel.CRITICAL
            elif load_ratio >= self.LOAD_CRITICAL:
                return SeverityLevel.HIGH
            elif load_ratio >= self.LOAD_HIGH:
                return SeverityLevel.MEDIUM
            else:
                return SeverityLevel.LOW
        
        # Default severity based on score
        if pressure_score >= 0.95:
            return SeverityLevel.CRITICAL
        elif pressure_score >= 0.8:
            return SeverityLevel.HIGH
        elif pressure_score >= 0.6:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def generate_summary(self, pressure_type: PressureType, metrics: Dict) -> str:
        """
        Generate natural language summary for Gemini 3.
        
        Args:
            pressure_type: Type of pressure
            metrics: System metrics
            
        Returns:
            Natural language summary
        """
        if pressure_type == PressureType.MEMORY_PRESSURE:
            available_pct = (metrics.get('mem_available_kb', 0) / 
                           metrics.get('mem_total_kb', 1) * 100)
            return f"Memory pressure: Only {available_pct:.1f}% available"
        
        elif pressure_type == PressureType.IO_CONGESTION:
            queue_depth = metrics.get('io_queue_depth', 0)
            return f"I/O congestion: Queue depth {queue_depth} ({queue_depth/self.max_io_queue*100:.0f}% of max)"
        
        elif pressure_type == PressureType.LOAD_MISMATCH:
            load = metrics.get('load_1min', 0)
            ratio = load / self.num_cpus
            return f"Load mismatch: {load:.1f} load on {self.num_cpus} cores ({ratio:.1f}× capacity)"
        
        elif pressure_type == PressureType.NETWORK_DEGRADATION:
            error_rate = self.calculate_network_health(metrics) * 5.0  # % errors
            return f"Network degradation: {error_rate:.2f}% packet error rate"
        
        elif pressure_type == PressureType.TCP_EXHAUSTION:
            time_wait = metrics.get('tcp_time_wait', 0)
            close_wait = metrics.get('tcp_close_wait', 0)
            return f"TCP exhaustion: {time_wait} TIME_WAIT, {close_wait} CLOSE_WAIT connections"
        
        elif pressure_type == PressureType.SWAP_THRASHING:
            swap_pct = (metrics.get('swap_used_kb', 0) / 
                       max(1, metrics.get('swap_total_kb', 1)) * 100)
            return f"Swap thrashing: {swap_pct:.1f}% swap used"
        
        else:
            return "System healthy"
    
    def detect_patterns(self, pressure_type: PressureType, metrics: Dict) -> List[str]:
        """
        Detect specific behavioral patterns.
        
        Args:
            pressure_type: Type of pressure
            metrics: System metrics
            
        Returns:
            List of pattern descriptions
        """
        patterns = []
        
        if pressure_type == PressureType.MEMORY_PRESSURE:
            dirty = metrics.get('dirty_kb', 0)
            writeback = metrics.get('writeback_kb', 0)
            if (dirty + writeback) > 1_000_000:  # >1GB dirty
                patterns.append("High dirty/writeback memory (I/O bottleneck)")
        
        if pressure_type == PressureType.TCP_EXHAUSTION:
            time_wait = metrics.get('tcp_time_wait', 0)
            established = metrics.get('tcp_established', 0)
            if time_wait > established * 10:
                patterns.append("TIME_WAIT >> ESTABLISHED (connection churning, not reusing)")
            
            close_wait = metrics.get('tcp_close_wait', 0)
            if close_wait > 100:
                patterns.append(f"{close_wait} CLOSE_WAIT connections (application not closing sockets)")
            
            syn_recv = metrics.get('tcp_syn_recv', 0)
            if syn_recv > 500:
                patterns.append(f"{syn_recv} SYN_RECV (possible SYN flood attack)")
        
        if pressure_type == PressureType.LOAD_MISMATCH:
            load = metrics.get('load_1min', 0)
            # This would need CPU idle % to determine
            # For now, just note the overload
            if load > self.num_cpus * 4:
                patterns.append("Extreme overload (4× CPU capacity)")
        
        return patterns
    
    def create_observation(self, metrics: Dict, timestamp: int = 0) -> SystemObservation:
        """
        Transform raw metrics into semantic observation.
        
        Args:
            metrics: System metrics dictionary
            timestamp: Timestamp of observation
            
        Returns:
            SystemObservation with semantic annotations
        """
        # Classify and calculate
        pressure_type = self.classify_pressure(metrics)
        
        # Get pressure score for primary type
        if pressure_type == PressureType.MEMORY_PRESSURE:
            pressure_score = self.calculate_memory_pressure(metrics)
        elif pressure_type == PressureType.IO_CONGESTION:
            pressure_score = self.calculate_io_congestion(metrics)
        elif pressure_type == PressureType.LOAD_MISMATCH:
            pressure_score = self.calculate_load_mismatch(metrics)
        elif pressure_type == PressureType.NETWORK_DEGRADATION:
            pressure_score = self.calculate_network_health(metrics)
        else:
            pressure_score = 0.0
        
        severity = self.assess_severity(pressure_type, pressure_score, metrics)
        summary = self.generate_summary(pressure_type, metrics)
        patterns = self.detect_patterns(pressure_type, metrics)
        
        # Reasoning hints
        reasoning_hints = []
        pattern_def = self.PATTERNS.get(pressure_type)
        if pattern_def:
            reasoning_hints = pattern_def.reasoning_hints.copy()
        
        return SystemObservation(
            timestamp=timestamp,
            pressure_type=pressure_type,
            severity=severity,
            summary=summary,
            patterns=patterns,
            reasoning_hints=reasoning_hints,
            pressure_score=pressure_score,
            metrics=metrics,
            context={}
        )


# Example usage
if __name__ == '__main__':
    classifier = SystemMetricsClassifier(num_cpus=4, max_io_queue=128)
    
    # Example: Memory pressure scenario
    metrics = {
        'mem_total_kb': 8_000_000,      # 8GB
        'mem_available_kb': 400_000,    # 400MB (5% available!)
        'mem_free_kb': 100_000,
        'cached_kb': 300_000,
        'load_1min': 2.5,
        'io_queue_depth': 45,
        'tcp_time_wait': 2500,
        'tcp_established': 50,
        'tcp_close_wait': 150
    }
    
    obs = classifier.create_observation(metrics, timestamp=1704470400000000000)
    
    print("System Observation:")
    print(f"  Summary: {obs.summary}")
    print(f"  Pressure Type: {obs.pressure_type.value}")
    print(f"  Severity: {obs.severity.value}")
    print(f"  Pressure Score: {obs.pressure_score:.2f}")
    print(f"  Patterns: {obs.patterns}")
    print(f"  Reasoning Hints:")
    for hint in obs.reasoning_hints:
        print(f"    - {hint}")

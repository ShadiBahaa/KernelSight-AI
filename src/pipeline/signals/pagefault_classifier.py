#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Page Fault Semantic Classifier

Transforms page fault events into behavioral observations for Gemini 3.
Categorizes memory access patterns (thrashing, normal paging, etc.) and adds semantic annotations.
"""

from typing import Dict, List
from enum import Enum
from dataclasses import dataclass, field


class PageFaultType(Enum):
    """Page fault behavioral types."""
    NORMAL_PAGING = "normal_paging"
    SWAP_THRASHING = "swap_thrashing"
    MEMORY_LEAK_INDICATOR = "memory_leak_indicator"
    COLD_START = "cold_start"
    EXCESSIVE_MAJOR_FAULTS = "excessive_major_faults"
    KERNEL_MEMORY_PRESSURE = "kernel_memory_pressure"


class SeverityLevel(Enum):
    """Severity of the page fault observation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PageFaultObservation:
    """Semantic observation from page fault events."""
    timestamp: int
    pid: int
    comm: str
    fault_type: PageFaultType
    severity: SeverityLevel
    summary: str  # Natural language summary for Gemini
    patterns: List[str]  # Behavioral patterns detected
    reasoning_hints: List[str]  # Suggested investigation paths
    metrics: Dict[str, float]  # Key metrics for this observation
    context: Dict[str, any] = field(default_factory=dict)


class PageFaultSemanticClassifier:
    """
    Classifies page fault behavior into semantic states and generates
    observations for agent reasoning.
    """
    
    # Major fault rate thresholds (faults per second)
    MAJOR_FAULT_RATE_LOW = 10        # <10/sec is normal
    MAJOR_FAULT_RATE_MEDIUM = 50     # 10-50/sec is concerning
    MAJOR_FAULT_RATE_HIGH = 100      # 50-100/sec is high
    MAJOR_FAULT_RATE_CRITICAL = 500  # >500/sec is thrashing
    
    # Latency thresholds (microseconds)
    LATENCY_NORMAL = 1000      # <1ms is expected for minor faults
    LATENCY_ELEVATED = 10000   # 1-10ms is elevated
    LATENCY_HIGH = 50000       # 10-50ms is high (disk I/O)
    LATENCY_CRITICAL = 100000  # >100ms is critical
    
    # Major fault percentage thresholds
    MAJOR_FAULT_PCT_LOW = 5      # <5% major faults is normal
    MAJOR_FAULT_PCT_MEDIUM = 20  # 5-20% is concerning
    MAJOR_FAULT_PCT_HIGH = 50    # >50% is critical (thrashing)
    
    def __init__(self):
        """Initialize classifier."""
        pass
    
    def classify_fault_type(self, metrics: Dict[str, float]) -> PageFaultType:
        """
        Classify page fault type based on metrics.
        
        Args:
            metrics: Dictionary with keys:
                - major_fault_rate (faults/sec)
                - minor_fault_rate (faults/sec)
                - avg_latency_us
                - major_fault_pct (percentage)
                
        Returns:
            PageFaultType enum
        """
        major_rate = metrics.get('major_fault_rate', 0)
        minor_rate = metrics.get('minor_fault_rate', 0)
        avg_latency = metrics.get('avg_latency_us', 0)
        major_pct = metrics.get('major_fault_pct', 0)
        
        # Check for swap thrashing (many major faults with high latency)
        if (major_rate > self.MAJOR_FAULT_RATE_CRITICAL and 
            avg_latency > self.LATENCY_HIGH):
            return PageFaultType.SWAP_THRASHING
        
        if (major_rate > self.MAJOR_FAULT_RATE_HIGH and
            major_pct > self.MAJOR_FAULT_PCT_HIGH):
            return PageFaultType.SWAP_THRASHING
        
        # Excessive major faults but not quite thrashing
        if major_rate > self.MAJOR_FAULT_RATE_HIGH:
            return PageFaultType.EXCESSIVE_MAJOR_FAULTS
        
        # Memory leak indicator: steadily increasing rate
        # (This would need historical tracking - simplified here)
        if major_rate > self.MAJOR_FAULT_RATE_MEDIUM:
            return PageFaultType.MEMORY_LEAK_INDICATOR
        
        # Cold start: high fault rate but decreasing
        if (major_rate + minor_rate > 100 and 
            major_pct < self.MAJOR_FAULT_PCT_LOW):
            return PageFaultType.COLD_START
        
        # Kernel memory pressure
        # (Would need kernel vs user mode tracking - simplified)
        
        # Default: normal paging
        return PageFaultType.NORMAL_PAGING
    
    def assess_severity(self, fault_type: PageFaultType, metrics: Dict[str, float]) -> SeverityLevel:
        """
        Determine severity based on fault type and metrics.
        
        Args:
            fault_type: Classified fault type
            metrics: Page fault metrics
            
        Returns:
            SeverityLevel enum
        """
        major_rate = metrics.get('major_fault_rate', 0)
        avg_latency = metrics.get('avg_latency_us', 0)
        
        if fault_type == PageFaultType.SWAP_THRASHING:
            if major_rate > self.MAJOR_FAULT_RATE_CRITICAL * 2:
                return SeverityLevel.CRITICAL
            elif major_rate > self.MAJOR_FAULT_RATE_CRITICAL:
                return SeverityLevel.HIGH
            return SeverityLevel.MEDIUM
        
        if fault_type == PageFaultType.EXCESSIVE_MAJOR_FAULTS:
            if major_rate > self.MAJOR_FAULT_RATE_CRITICAL:
                return SeverityLevel.HIGH
            elif major_rate > self.MAJOR_FAULT_RATE_HIGH:
                return SeverityLevel.MEDIUM
            return SeverityLevel.LOW
        
        if fault_type == PageFaultType.MEMORY_LEAK_INDICATOR:
            return SeverityLevel.MEDIUM
        
        if fault_type == PageFaultType.COLD_START:
            return SeverityLevel.LOW
        
        # Normal paging
        return SeverityLevel.LOW
    
    def generate_summary(self, comm: str, fault_type: PageFaultType, 
                        metrics: Dict[str, float]) -> str:
        """
        Generate natural language summary for Gemini 3.
        
        Args:
            comm: Process name
            fault_type: Fault type
            metrics: Page fault metrics
            
        Returns:
            Natural language summary
        """
        major_rate = metrics.get('major_fault_rate', 0)
        minor_rate = metrics.get('minor_fault_rate', 0)
        avg_latency = metrics.get('avg_latency_us', 0)
        major_pct = metrics.get('major_fault_pct', 0)
        
        if fault_type == PageFaultType.SWAP_THRASHING:
            return (f"Swap thrashing detected: {comm} experiencing {major_rate:.0f} major faults/sec "
                   f"({major_pct:.0f}% of total) with {avg_latency/1000:.1f}ms avg latency")
        
        elif fault_type == PageFaultType.EXCESSIVE_MAJOR_FAULTS:
            return (f"Excessive major page faults: {comm} triggering {major_rate:.0f} disk I/O operations/sec")
        
        elif fault_type == PageFaultType.MEMORY_LEAK_INDICATOR:
            return (f"Potential memory leak: {comm} showing elevated major fault rate ({major_rate:.0f}/sec)")
        
        elif fault_type == PageFaultType.COLD_START:
            return (f"Cold start pattern: {comm} loading pages into memory "
                   f"({major_rate + minor_rate:.0f} faults/sec)")
        
        elif fault_type == PageFaultType.KERNEL_MEMORY_PRESSURE:
            return f"Kernel memory pressure: {comm} experiencing kernel-mode page faults"
        
        else:  # NORMAL_PAGING
            return f"{comm} normal paging behavior ({minor_rate:.0f} minor faults/sec)"
    
    def detect_patterns(self, fault_type: PageFaultType, metrics: Dict[str, float]) -> List[str]:
        """
        Detect specific behavioral patterns.
        
        Args:
            fault_type: Fault type
            metrics: Page fault metrics
            
        Returns:
            List of pattern descriptions
        """
        patterns = []
        
        major_rate = metrics.get('major_fault_rate', 0)
        minor_rate = metrics.get('minor_fault_rate', 0)
        avg_latency = metrics.get('avg_latency_us', 0)
        major_pct = metrics.get('major_fault_pct', 0)
        
        # Swap activity indicator
        if major_rate > self.MAJOR_FAULT_RATE_MEDIUM:
            patterns.append(f"Pages being swapped to/from disk ({major_rate:.0f} major faults/sec)")
        
        # High latency indicator
        if avg_latency > self.LATENCY_HIGH:
            patterns.append(f"Slow page fault handling ({avg_latency/1000:.1f}ms average) - disk I/O bottleneck")
        
        # High major fault percentage
        if major_pct > self.MAJOR_FAULT_PCT_HIGH:
            patterns.append(f"{major_pct:.0f}% major faults - working set exceeds physical memory")
        
        # Memory pressure indicator
        if major_rate + minor_rate > 1000:
            patterns.append("Very high page fault rate - memory pressure or large working set")
        
        # Write faults (if available)
        write_pct = metrics.get('write_fault_pct', 0)
        if write_pct > 50:
            patterns.append(f"{write_pct:.0f}% write faults - copy-on-write or dirty page eviction")
        
        return patterns
    
    def create_observation(self, event: Dict) -> PageFaultObservation:
        """
        Transform raw page fault event into semantic observation.
        
        This method processes a single page fault event.
        For aggregate analysis, you'd need to accumulate events over time.
        
        Args:
            event: Raw page fault event dictionary with keys:
                - timestamp, pid, tid, address, latency_ns, cpu,
                  is_major, is_write, is_kernel, comm
                  
        Returns:
            PageFaultObservation with semantic annotations
        """
        # For single event, we can only do limited analysis
        # Ideally, this would aggregate multiple events over time
        
        pid = event.get('pid', 0)
        comm = event.get('comm', 'unknown')
        is_major = event.get('is_major', 0)
        latency_us = event.get('latency_ns', 0) / 1000.0  # Convert to microseconds
        is_write = event.get('is_write', 0)
        is_kernel = event.get('is_kernel', 0)
        
        # Simple single-event metrics
        metrics = {
            'latency_us': latency_us,
            'is_major': float(is_major),
            'is_write': float(is_write),
            'is_kernel': float(is_kernel),
            # For proper analysis, these would come from aggregation:
            'major_fault_rate': 0.0,  # Would need time window
            'minor_fault_rate': 0.0,
            'avg_latency_us': latency_us,
            'major_fault_pct': 100.0 if is_major else 0.0,
            'write_fault_pct': 100.0 if is_write else 0.0
        }
        
        # Classify based on single event characteristics
        # Note: This is simplified - real classification needs aggregation
        if is_major and latency_us > self.LATENCY_HIGH:
            fault_type = PageFaultType.SWAP_THRASHING
            severity = SeverityLevel.HIGH
        elif is_major and latency_us > self.LATENCY_ELEVATED:
            fault_type = PageFaultType.EXCESSIVE_MAJOR_FAULTS
            severity = SeverityLevel.MEDIUM
        elif is_major:
            fault_type = PageFaultType.MEMORY_LEAK_INDICATOR
            severity = SeverityLevel.LOW
        else:
            fault_type = PageFaultType.NORMAL_PAGING
            severity = SeverityLevel.LOW
        
        # Generate semantic content
        if is_major and latency_us > self.LATENCY_HIGH:
            summary = f"Major page fault: {comm} blocked for {latency_us/1000:.1f}ms loading page from disk"
        elif is_major:
            summary = f"Major page fault: {comm} loaded page from disk ({latency_us/1000:.1f}ms)"
        else:
            summary = f"Minor page fault: {comm} loaded page from cache ({latency_us:.0f}μs)"
        
        patterns = []
        if is_major:
            patterns.append("Page not in memory - disk I/O required")
        if latency_us > self.LATENCY_HIGH:
            patterns.append(f"Slow fault handling ({latency_us/1000:.1f}ms) - possible disk contention")
        if is_write:
            patterns.append("Copy-on-write or dirty page eviction")
        if is_kernel:
            patterns.append("Kernel-mode page fault")
        
        # Reasoning hints
        reasoning_hints = [
            "Correlate with memory pressure metrics",
            "Check swap usage and I/O latency",
            "Identify processes with highest fault rates"
        ]
        
        if is_major and latency_us > self.LATENCY_HIGH:
            reasoning_hints.insert(0, "High major fault latency indicates swap thrashing or disk bottleneck")
        
        # Context
        context = {
            'pid': pid,
            'comm': comm,
            'address': event.get('address'),
            'cpu': event.get('cpu'),
            'is_major': is_major,
            'is_write': is_write,
            'is_kernel': is_kernel
        }
        
        return PageFaultObservation(
            timestamp=event.get('timestamp', 0),
            pid=pid,
            comm=comm,
            fault_type=fault_type,
            severity=severity,
            summary=summary,
            patterns=patterns,
            reasoning_hints=reasoning_hints,
            metrics=metrics,
            context=context
        )


# Example usage
if __name__ == '__main__':
    classifier = PageFaultSemanticClassifier()
    
    # Example: Major page fault with high latency (swap thrashing)
    event = {
        'timestamp': 1704470400000000000,
        'pid': 1234,
        'tid': 1234,
        'comm': 'mysql',
        'address': 0x7fff12345000,
        'latency_ns': 85000000,  # 85ms!
        'cpu': 2,
        'is_major': 1,
        'is_write': 0,
        'is_kernel': 0
    }
    
    obs = classifier.create_observation(event)
    
    print("Page Fault Observation:")
    print(f"  Summary: {obs.summary}")
    print(f"  Fault Type: {obs.fault_type.value}")
    print(f"  Severity: {obs.severity.value}")
    print(f"  Patterns:")
    for pattern in obs.patterns:
        print(f"    - {pattern}")
    print(f"  Reasoning Hints:")
    for hint in obs.reasoning_hints:
        print(f"    - {hint}")

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Scheduler Semantic Classifier

Transforms raw scheduler events into behavioral observations for Gemini 3.
Categorizes scheduler patterns (CPU starvation, thrashing, normal) and adds semantic annotations.
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class SchedulerState(Enum):
    """Scheduler behavioral states."""
    NORMAL = "normal"
    BUSY = "busy"
    THRASHING = "thrashing"
    CPU_STARVATION = "cpu_starvation"
    LOCK_CONTENTION_INDUCED = "lock_contention_induced"
    IMBALANCED = "imbalanced"


class SeverityLevel(Enum):
    """Severity of the scheduler observation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SchedulerPattern:
    """Describes what a scheduler pattern means for the agent."""
    state: SchedulerState
    description: str
    typical_causes: List[str]
    agent_interpretation: str
    reasoning_hints: List[str]


@dataclass
class SchedulerObservation:
    """Semantic observation from scheduler events."""
    timestamp: int
    pid: int
    comm: str
    state: SchedulerState
    severity: SeverityLevel
    summary: str  # Natural language summary for Gemini
    patterns: List[str]  # Behavioral patterns detected
    reasoning_hints: List[str]  # Suggested investigation paths
    metrics: Dict[str, float]  # Key metrics for this observation
    context: Dict[str, any] = field(default_factory=dict)  # Additional context


class SchedulerSemanticClassifier:
    """
    Classifies scheduler behavior into semantic states and generates
    observations for agent reasoning.
    """
    
    # Thresholds for pattern detection
    # Context switch rates (per second)
    CS_RATE_LOW = 100
    CS_RATE_MEDIUM = 1000
    CS_RATE_HIGH = 5000
    CS_RATE_CRITICAL = 10000
    
    # Involuntary switch percentage
    INVOLUNTARY_NORMAL = 30  # Below 30% is normal
    INVOLUNTARY_HIGH = 60    # 30-60% is concerning
    INVOLUNTARY_CRITICAL = 80  # Above 80% is critical
    
    # Wakeup to context switch ratio
    WAKEUP_CS_RATIO_LOW = 0.5      # Efficient: Most wakeups lead to execution
    WAKEUP_CS_RATIO_HIGH = 2.0     # Inefficient: Many wakeups, few switches
    WAKEUP_CS_RATIO_THRASH = 5.0   # Thrashing: Many wakeups, almost no execution
    
    # Average timeslice (milliseconds)
    TIMESLICE_SHORT = 1      # <1ms is very short
    TIMESLICE_NORMAL_MIN = 1    # 1-10ms is normal
    TIMESLICE_NORMAL_MAX = 10
    TIMESLICE_LONG = 50      # >50ms might indicate lock holding
    
    # Behavioral pattern descriptions
    PATTERNS = {
        SchedulerState.NORMAL: SchedulerPattern(
            state=SchedulerState.NORMAL,
            description="Healthy scheduler behavior",
            typical_causes=[
                "Normal workload",
                "Balanced CPU usage",
                "Efficient context switching"
            ],
            agent_interpretation="Scheduler operating normally",
            reasoning_hints=[
                "No action needed",
                "Use as baseline for comparison"
            ]
        ),
        SchedulerState.BUSY: SchedulerPattern(
            state=SchedulerState.BUSY,
            description="High CPU utilization but not pathological",
            typical_causes=[
                "CPU-bound workload",
                "Many runnable processes",
                "High throughput demand"
            ],
            agent_interpretation="System under load but functioning normally",
            reasoning_hints=[
                "Monitor for transition to thrashing",
                "Check if load is expected (batch job, traffic spike)",
                "Verify runqueue depth is proportional to core count"
            ]
        ),
        SchedulerState.THRASHING: SchedulerPattern(
            state=SchedulerState.THRASHING,
            description="Excessive context switching with minimal productive work",
            typical_causes=[
                "Too many short-lived tasks",
                "Lock contention causing rapid wake/sleep cycles",
                "Thundering herd problem",
                "Process explosion (fork bomb)"
            ],
            agent_interpretation="Scheduling thrash: CPU cycles wasted on context switching",
            reasoning_hints=[
                "Identify processes with highest context switch rates",
                "Check for futex contention (correlate with syscall events)",
                "Look for process count explosion",
                "Monitor involuntary switch percentage"            ]
        ),
        SchedulerState.CPU_STARVATION: SchedulerPattern(
            state=SchedulerState.CPU_STARVATION,
            description="Processes not getting CPU time despite being runnable",
            typical_causes=[
                "Runqueue depth >> core count",
                "High-priority processes monopolizing CPU",
                "Scheduler imbalance (uneven load across CPUs)",
                "CPU affinity pinning many tasks to few cores"
            ],
            agent_interpretation="CPU starvation: Processes blocked waiting for CPU time",
            reasoning_hints=[
                "Check runqueue depth vs core count",
                "Identify processes with longest wait times",
                "Look for CPU affinity issues",
                "Correlate with load average metrics"
            ]
        ),
        SchedulerState.LOCK_CONTENTION_INDUCED: SchedulerPattern(
            state=SchedulerState.LOCK_CONTENTION_INDUCED,
            description="Scheduler churn caused by lock contention",
            typical_causes=[
                "Many threads waking up to acquire locks",
                "Lock holder making slow progress",
                "Thundering herd on lock release"
            ],
            agent_interpretation="Lock contention cascade: Threads rapidly waking and sleeping",
            reasoning_hints=[
                "Correlate with futex syscall latency",
                "Check wakeup-to-switch ratio (high indicates blocking)",
                "Identify lock owner (if possible)",
                "Look for shared resources being accessed"
            ]
        ),
        SchedulerState.IMBALANCED: SchedulerPattern(
            state=SchedulerState.IMBALANCED,
            description="Uneven CPU load distribution",
            typical_causes=[
                "CPU affinity pinning",
                "NUMA effects",
                "Scheduler failing to migrate tasks",
                "Asymmetric workload"
            ],
            agent_interpretation="Scheduler imbalance: Uneven load across CPUs",
            reasoning_hints=[
                "Check per-CPU runqueue depths",
                "Verify CPU affinity settings",
                "Look for NUMA node imbalances",
                "Consider load balancer tuning"
            ]
        )
    }
    
    def __init__(self, num_cpus: int = 4):
        """
        Initialize classifier.
        
        Args:
            num_cpus: Number of CPU cores (for load calculations)
        """
        self.num_cpus = num_cpus
    
    def classify_state(self, metrics: Dict[str, float]) -> SchedulerState:
        """
        Classify scheduler state based on metrics.
        
        Args:
            metrics: Dictionary with keys:
                - context_switches_per_sec
                - involuntary_pct
                - wakeup_to_cs_ratio
                - avg_timeslice_ms
                - runqueue_depth (optional)
                
        Returns:
            SchedulerState enum
        """
        cs_rate = metrics.get('context_switches_per_sec', 0)
        involuntary_pct = metrics.get('involuntary_pct', 0)
        wakeup_cs_ratio = metrics.get('wakeup_to_cs_ratio', 0)
        avg_timeslice = metrics.get('avg_timeslice_ms', 10)
        runqueue_depth = metrics.get('runqueue_depth', 0)
        
        # Check for thrashing (highest priority)
        if (cs_rate > self.CS_RATE_CRITICAL and 
            avg_timeslice < self.TIMESLICE_SHORT):
            return SchedulerState.THRASHING
        
        # Check for CPU starvation
        if runqueue_depth > 0 and runqueue_depth > self.num_cpus * 3:
            return SchedulerState.CPU_STARVATION
        
        # Check for lock contention induced churn
        if (wakeup_cs_ratio > self.WAKEUP_CS_RATIO_HIGH and
            involuntary_pct < self.INVOLUNTARY_NORMAL):
            # High wakeups but low involuntary = processes blocking on something
            return SchedulerState.LOCK_CONTENTION_INDUCED
        
        # Check for general thrashing
        if (cs_rate > self.CS_RATE_HIGH and 
            involuntary_pct > self.INVOLUNTARY_CRITICAL):
            return SchedulerState.THRASHING
        
        # Check for busy but healthy
        if cs_rate > self.CS_RATE_MEDIUM:
            return SchedulerState.BUSY
        
        # Default: normal
        return SchedulerState.NORMAL
    
    def assess_severity(self, state: SchedulerState, metrics: Dict[str, float]) -> SeverityLevel:
        """
        Determine severity based on state and metrics.
        
        Args:
            state: Classified scheduler state
            metrics: Scheduler metrics
            
        Returns:
            SeverityLevel enum
        """
        cs_rate = metrics.get('context_switches_per_sec', 0)
        involuntary_pct = metrics.get('involuntary_pct', 0)
        
        if state == SchedulerState.NORMAL:
            return SeverityLevel.LOW
        
        if state == SchedulerState.BUSY:
            if cs_rate > self.CS_RATE_HIGH:
                return SeverityLevel.MEDIUM
            return SeverityLevel.LOW
        
        if state == SchedulerState.THRASHING:
            if cs_rate > self.CS_RATE_CRITICAL * 2:
                return SeverityLevel.CRITICAL
            elif cs_rate > self.CS_RATE_CRITICAL:
                return SeverityLevel.HIGH
            return SeverityLevel.MEDIUM
        
        if state == SchedulerState.CPU_STARVATION:
            runqueue_depth = metrics.get('runqueue_depth', 0)
            if runqueue_depth > self.num_cpus * 10:
                return SeverityLevel.CRITICAL
            elif runqueue_depth > self.num_cpus * 5:
                return SeverityLevel.HIGH
            return SeverityLevel.MEDIUM
        
        if state == SchedulerState.LOCK_CONTENTION_INDUCED:
            if involuntary_pct > self.INVOLUNTARY_CRITICAL:
                return SeverityLevel.HIGH
            return SeverityLevel.MEDIUM
        
        if state == SchedulerState.IMBALANCED:
            return SeverityLevel.MEDIUM
        
        return SeverityLevel.LOW
    
    def generate_summary(self, comm: str, state: SchedulerState, 
                        metrics: Dict[str, float]) -> str:
        """
        Generate natural language summary for Gemini 3.
        
        Args:
            comm: Process name
            state: Scheduler state
            metrics: Scheduler metrics
            
        Returns:
            Natural language summary
        """
        pattern = self.PATTERNS.get(state)
        cs_rate = metrics.get('context_switches_per_sec', 0)
        involuntary_pct = metrics.get('involuntary_pct', 0)
        
        if state == SchedulerState.THRASHING:
            return (f"Scheduling thrash detected: {comm} switching {cs_rate:.0f} times/sec "
                   f"({involuntary_pct:.0f}% involuntary)")
        
        elif state == SchedulerState.CPU_STARVATION:
            runqueue_depth = metrics.get('runqueue_depth', 0)
            return (f"CPU starvation: {comm} waiting for CPU (runqueue depth: {runqueue_depth:.0f} "
                   f"vs {self.num_cpus} cores)")
        
        elif state == SchedulerState.LOCK_CONTENTION_INDUCED:
            wakeup_cs_ratio = metrics.get('wakeup_to_cs_ratio', 0)
            return (f"Lock contention cascade: {comm} waking {wakeup_cs_ratio:.1f}× more than switching "
                   f"(blocking on resources)")
        
        elif state == SchedulerState.BUSY:
            return f"High CPU load: {comm} switching {cs_rate:.0f} times/sec (normal for busy system)"
        
        elif state == SchedulerState.IMBALANCED:
            return f"Scheduler imbalance detected for {comm}"
        
        else:  # NORMAL
            return f"{comm} scheduler behavior normal"
    
    def detect_patterns(self, state: SchedulerState, metrics: Dict[str, float]) -> List[str]:
        """
        Detect specific behavioral patterns.
        
        Args:
            state: Scheduler state
            metrics: Scheduler metrics
            
        Returns:
            List of pattern descriptions
        """
        patterns = []
        
        cs_rate = metrics.get('context_switches_per_sec', 0)
        involuntary_pct = metrics.get('involuntary_pct', 0)
        wakeup_cs_ratio = metrics.get('wakeup_to_cs_ ratio', 0)
        avg_timeslice = metrics.get('avg_timeslice_ms', 10)
        
        # Very short timeslices
        if avg_timeslice < self.TIMESLICE_SHORT:
           patterns.append(f"Very short timeslices ({avg_timeslice:.2f}ms) - rapid preemption")
        
        # High involuntary switches
        if involuntary_pct > self.INVOLUNTARY_CRITICAL:
            patterns.append(f"{involuntary_pct:.0f}% involuntary switches - processes forced off CPU")
        
        # Thundering herd indicator
        if wakeup_cs_ratio > self.WAKEUP_CS_RATIO_THRASH:
            patterns.append("Thundering herd pattern - many wakeups but little execution")
        
        # Lock blocking indicator
        if wakeup_cs_ratio > self.WAKEUP_CS_RATIO_HIGH and involuntary_pct < self.INVOLUNTARY_NORMAL:
            patterns.append("Processes waking but immediately blocking (likely lock contention)")
        
        # Excessive context switching
        if cs_rate > self.CS_RATE_CRITICAL:
            patterns.append(f"Excessive context switching ({cs_rate:.0f}/sec)")
        
        return patterns
    
    def create_observation(self, event: Dict) -> SchedulerObservation:
        """
        Transform raw scheduler event into semantic observation.
        
        Args:
            event: Raw scheduler event dictionary with keys:
                - time_bucket, pid, comm, context_switches, voluntary_switches,
                  involuntary_switches, wakeups, cpu_time_ns, total_timeslice_ns,
                  timeslice_count
                  
        Returns:
            SchedulerObservation with semantic annotations
        """
        # Extract event data
        pid = event.get('pid', 0)
        comm = event.get('comm', 'unknown')
        cs_total = event.get('context_switches', 0)
        cs_voluntary = event.get('voluntary_switches', 0)
        cs_involuntary = event.get('involuntary_switches', 0)
        wakeups = event.get('wakeups', 0)
        total_timeslice_ns = event.get('total_timeslice_ns', 0)
        timeslice_count = event.get('timeslice_count', 0)
        
        # Calculate metrics
        cs_rate = cs_total  # Already per-second (1-second bucket)
        involuntary_pct = (cs_involuntary / cs_total * 100) if cs_total > 0 else 0
        wakeup_cs_ratio = (wakeups / cs_total) if cs_total > 0 else 0
        avg_timeslice_ms = (total_timeslice_ns / timeslice_count / 1_000_000) if timeslice_count > 0 else 10
        
        metrics = {
            'context_switches_per_sec': cs_rate,
            'involuntary_pct': involuntary_pct,
            'wakeup_to_cs_ratio': wakeup_cs_ratio,
            'avg_timeslice_ms': avg_timeslice_ms,
            'voluntary_switches': cs_voluntary,
            'involuntary_switches': cs_involuntary,
            'wakeups': wakeups
        }
        
        # Classify and assess
        state = self.classify_state(metrics)
        severity = self.assess_severity(state, metrics)
        
        # Generate semantic content
        summary = self.generate_summary(comm, state, metrics)
        patterns = self.detect_patterns(state, metrics)
        
        # Reasoning hints from pattern
        reasoning_hints = []
        pattern_def = self.PATTERNS.get(state)
        if pattern_def:
            reasoning_hints = pattern_def.reasoning_hints.copy()
        
        # Context
        context = {
            'pid': pid,
            'comm': comm,
            'time_bucket': event.get('time_bucket'),
            'cpu_time_ns': event.get('cpu_time_ns', 0)
        }
        
        return SchedulerObservation(
            timestamp=event.get('time_bucket', 0) * 1_000_000_000,  # Convert to ns
            pid=pid,
            comm=comm,
            state=state,
            severity=severity,
            summary=summary,
            patterns=patterns,
            reasoning_hints=reasoning_hints,
            metrics=metrics,
            context=context
        )
    
    def get_pattern_description(self, state: SchedulerState) -> Optional[SchedulerPattern]:
        """
        Get behavioral pattern description for a state.
        
        Args:
            state: Scheduler state
            
        Returns:
            SchedulerPattern or None
        """
        return self.PATTERNS.get(state)


# Example usage
if __name__ == '__main__':
    classifier = SchedulerSemanticClassifier(num_cpus=4)
    
    # Example 1: Thrashing scenario
    thrash_event = {
        'time_bucket': 12345,
        'pid': 1234,
        'comm': 'stress',
        'context_switches': 15000,  # Very high
        'voluntary_switches': 2000,
        'involuntary_switches': 13000,  # 87% involuntary
        'wakeups': 8000,
        'cpu_time_ns': 500_000_000,  # 500ms total
        'total_timeslice_ns': 15_000_000,  # 15ms total
        'timeslice_count': 15000  # 1μs average!
    }
    
    obs = classifier.create_observation(thrash_event)
    print("Scheduler Observation (Thrashing):")
    print(f"  Summary: {obs.summary}")
    print(f"  State: {obs.state.value}")
    print(f"  Severity: {obs.severity.value}")
    print(f"  Metrics:")
    for k, v in obs.metrics.items():
        print(f"    {k}: {v:.2f}")
    print(f"  Patterns: {obs.patterns}")
    print(f"  Reasoning Hints:")
    for hint in obs.reasoning_hints:
        print(f"    - {hint}")

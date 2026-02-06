#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Signal Interpreter Layer

Transforms numeric features into natural language observations for Gemini 3.
Tracks persistence duration and generates narratives instead of raw metrics.
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import time


class ObservationType(Enum):
    """Types of observations."""
    MEMORY_PRESSURE = "memory_pressure"
    IO_BOTTLENECK = "io_bottleneck"
    CPU_CONTENTION = "cpu_contention"
    NETWORK_DEGRADATION = "network_degradation"
    ANOMALY = "anomaly"
    BASELINE = "baseline"


class SeverityLevel(Enum):
    """Observation severity."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Observation:
    """Natural language observation for agent."""
    type: ObservationType
    severity: SeverityLevel
    narrative: str  # Natural language description
    duration_seconds: float  # How long this has persisted
    first_seen: float  # Timestamp when first observed
    last_seen: float  # Timestamp of latest observation
    evidence: Dict[str, any]  # Supporting data
    recommendations: List[str]  # Suggested actions


class SignalInterpreter:
    """
    Interprets numeric features as natural language observations.
    Tracks persistence and generates narratives for Gemini 3.
    """
    
    # Z-score thresholds for severity
    ZSCORE_LOW = 2.0
    ZSCORE_MEDIUM = 3.0
    ZSCORE_HIGH = 4.0
    ZSCORE_CRITICAL = 5.0
    
    # Persistence thresholds (seconds)
    PERSISTENCE_TRANSIENT = 60      # <1 minute
    PERSISTENCE_SHORT = 300         # 1-5 minutes
    PERSISTENCE_PERSISTENT = 900    # 5-15 minutes
    PERSISTENCE_SYSTEMIC = 900      # >15 minutes
    
    def __init__(self):
        """Initialize interpreter."""
        # Track when each observation type was first seen
        self._first_seen: Dict[str, float] = {}
        # Track historical states for trending
        self._history: Dict[str, List[float]] = {}
    
    def interpret(self, features: Dict[str, any], 
                  baseline_stats: Optional[Dict[str, Dict[str, float]]] = None,
                  timestamp: Optional[float] = None) -> List[Observation]:
        """
        Interpret features as natural language observations.
        
        Args:
            features: Current feature values (from FeatureExporter.get_current_state())
            baseline_stats: Baseline statistics {feature: {mean, std}}
            timestamp: Observation timestamp (default: now)
            
        Returns:
            List of observations
        """
        if timestamp is None:
            timestamp = time.time()
        
        observations = []
        
        # Memory pressure observation
        mem_obs = self._interpret_memory(features, baseline_stats, timestamp)
        if mem_obs:
            observations.append(mem_obs)
        
        # I/O bottleneck observation
        io_obs = self._interpret_io(features, baseline_stats, timestamp)
        if io_obs:
            observations.append(io_obs)
        
        # CPU contention observation
        cpu_obs = self._interpret_cpu(features, baseline_stats, timestamp)
        if cpu_obs:
            observations.append(cpu_obs)
        
        # Network degradation observation
        net_obs = self._interpret_network(features, baseline_stats, timestamp)
        if net_obs:
            observations.append(net_obs)
        
        # Generic anomalies (anything with high z-score not covered above)
        anomaly_obs = self._interpret_anomalies(features, baseline_stats, timestamp)
        observations.extend(anomaly_obs)
        
        return observations
    
    def _interpret_memory(self, features, baseline_stats, timestamp) -> Optional[Observation]:
        """Interpret memory-related features."""
        mem_features = {k: v for k, v in features.items() 
                       if 'memory' in k or 'swap' in k}
        
        if not mem_features:
            return None
        
        # Calculate z-scores for memory features
        zscores = self._calculate_zscores(mem_features, baseline_stats)
        
        # Check for memory pressure
        pressure_indicators = [
            'memory_pressure',
            'memory_available_pct',
            'swap_used_pct'
        ]
        
        max_zscore = 0
        pressure_feature = None
        
        for feature in pressure_indicators:
            if feature in zscores and abs(zscores[feature]) > abs(max_zscore):
                max_zscore = zscores[feature]
                pressure_feature = feature
        
        if abs(max_zscore) < self.ZSCORE_LOW:
            return None  # No significant memory pressure
        
        # Determine severity
        severity = self._zscore_to_severity(abs(max_zscore))
        
        # Calculate persistence duration
        obs_key = "memory_pressure"
        duration = self._calculate_persistence(obs_key, timestamp)
        
        # Generate narrative
        narrative = self._generate_memory_narrative(
            pressure_feature, features.get(pressure_feature),
            max_zscore, duration
        )
        
        # Recommendations
        recommendations = [
            "Identify processes with highest memory usage",
            "Check for memory leaks (steadily increasing RSS)",
            "Correlate with deployment or workload changes"
        ]
        
        if 'swap' in pressure_feature:
            recommendations.insert(0, "Critical: System swapping to disk - severe performance impact")
        
        return Observation(
            type=ObservationType.MEMORY_PRESSURE,
            severity=severity,
            narrative=narrative,
            duration_seconds=duration,
            first_seen=self._first_seen.get(obs_key, timestamp),
            last_seen=timestamp,
            evidence={'feature': pressure_feature, 'value': features.get(pressure_feature),
                     'zscore': max_zscore, 'all_memory_features': mem_features},
            recommendations=recommendations
        )
    
    def _interpret_io(self, features, baseline_stats, timestamp) -> Optional[Observation]:
        """Interpret I/O-related features."""
        io_features = {k: v for k, v in features.items() 
                      if 'io' in k or 'read' in k or 'write' in k or 'latency' in k}
        
        if not io_features:
            return None
        
        zscores = self._calculate_zscores(io_features, baseline_stats)
        
        # Look for latency spikes
        latency_features = [k for k in zscores if 'latency' in k or 'p95' in k or 'p99' in k]
        
        max_zscore = 0
        bottleneck_feature = None
        
        for feature in latency_features:
            if abs(zscores[feature]) > abs(max_zscore):
                max_zscore = zscores[feature]
                bottleneck_feature = feature
        
        if abs(max_zscore) < self.ZSCORE_LOW:
            return None
        
        severity = self._zscore_to_severity(abs(max_zscore))
        obs_key = "io_bottleneck"
        duration = self._calculate_persistence(obs_key, timestamp)
        
        narrative = self._generate_io_narrative(
            bottleneck_feature, features.get(bottleneck_feature),
            max_zscore, duration
        )
        
        recommendations = [
            "Check disk saturation (queue depth, IOPS)",
            "Identify processes with highest I/O rate",
            "Look for random vs sequential access patterns",
            "Correlate with block_stats and syscall I/O events"
        ]
        
        return Observation(
            type=ObservationType.IO_BOTTLENECK,
            severity=severity,
            narrative=narrative,
            duration_seconds=duration,
            first_seen=self._first_seen.get(obs_key, timestamp),
            last_seen=timestamp,
            evidence={'feature': bottleneck_feature, 'value': features.get(bottleneck_feature),
                     'zscore': max_zscore},
            recommendations=recommendations
        )
    
    def _interpret_cpu(self, features, baseline_stats, timestamp) -> Optional[Observation]:
        """Interpret CPU/scheduler-related features."""
        cpu_features = {k: v for k, v in features.items() 
                       if 'cpu' in k or 'load' in k or 'context_switch' in k or 'sched' in k}
        
        if not cpu_features:
            return None
        
        zscores = self._calculate_zscores(cpu_features, baseline_stats)
        
        # Look for context switch spikes or load spikes
        contention_features = [k for k in zscores if 'context_switch' in k or 'load' in k]
        
        max_zscore = 0
        contention_feature = None
        
        for feature in contention_features:
            if abs(zscores[feature]) > abs(max_zscore):
                max_zscore = zscores[feature]
                contention_feature = feature
        
        if abs(max_zscore) < self.ZSCORE_LOW:
            return None
        
        severity = self._zscore_to_severity(abs(max_zscore))
        obs_key = "cpu_contention"
        duration = self._calculate_persistence(obs_key, timestamp)
        
        narrative = self._generate_cpu_narrative(
            contention_feature, features.get(contention_feature),
            max_zscore, duration
        )
        
        recommendations = [
            "Identify processes with highest context switch rates",
            "Check for scheduler thrashing or process explosion",
            "Correlate with sched_events for patterns",
            "Monitor runqueue depth vs core count"
        ]
        
        return Observation(
            type=ObservationType.CPU_CONTENTION,
            severity=severity,
            narrative=narrative,
            duration_seconds=duration,
            first_seen=self._first_seen.get(obs_key, timestamp),
            last_seen=timestamp,
            evidence={'feature': contention_feature, 'value': features.get(contention_feature),
                     'zscore': max_zscore},
            recommendations=recommendations
        )
    
    def _interpret_network(self, features, baseline_stats, timestamp) -> Optional[Observation]:
        """Interpret network-related features."""
        net_features = {k: v for k, v in features.items() 
                       if 'network' in k or 'tcp' in k or 'rx' in k or 'tx' in k}
        
        if not net_features:
            return None
        
        zscores = self._calculate_zscores(net_features, baseline_stats)
        
        # Look for error rates or TCP issues
        degradation_features = [k for k in zscores if 'error' in k or 'drop' in k or 'retrans' in k]
        
        max_zscore = 0
        degradation_feature = None
        
        for feature in degradation_features:
            if abs(zscores[feature]) > abs(max_zscore):
                max_zscore = zscores[feature]
                degradation_feature = feature
        
        if abs(max_zscore) < self.ZSCORE_LOW:
            return None
        
        severity = self._zscore_to_severity(abs(max_zscore))
        obs_key = "network_degradation"
        duration = self._calculate_persistence(obs_key, timestamp)
        
        narrative = self._generate_network_narrative(
            degradation_feature, features.get(degradation_feature),
            max_zscore, duration
        )
        
        recommendations = [
            "Check physical network connectivity",
            "Monitor error types (RX vs TX)",
            "Correlate with network syscall latency",
            "Look for retransmit rates and packet loss"
        ]
        
        return Observation(
            type=ObservationType.NETWORK_DEGRADATION,
            severity=severity,
            narrative=narrative,
            duration_seconds=duration,
            first_seen=self._first_seen.get(obs_key, timestamp),
            last_seen=timestamp,
            evidence={'feature': degradation_feature, 'value': features.get(degradation_feature),
                     'zscore': max_zscore},
            recommendations=recommendations
        )
    
    def _interpret_anomalies(self, features, baseline_stats, timestamp) -> List[Observation]:
        """Catch-all for other anomalies."""
        if not baseline_stats:
            return []
        
        zscores = self._calculate_zscores(features, baseline_stats)
        
        # Find features with high z-scores not already covered
        covered_keywords = ['memory', 'swap', 'io', 'latency', 'cpu', 'load', 
                           'context_switch', 'sched', 'network', 'tcp', 'rx', 'tx']
        
        anomalies = []
        for feature, zscore in zscores.items():
            if abs(zscore) >= self.ZSCORE_MEDIUM:
                # Check if already covered
                if any(kw in feature.lower() for kw in covered_keywords):
                    continue
                
                severity = self._zscore_to_severity(abs(zscore))
                obs_key = f"anomaly_{feature}"
                duration = self._calculate_persistence(obs_key, timestamp)
                
                narrative = f"Anomalous behavior detected in {feature}: {zscore:.1f}sigma from baseline"
                if duration > 60:
                    narrative += f" (persisting for {self._format_duration(duration)})"
                
                anomalies.append(Observation(
                    type=ObservationType.ANOMALY,
                    severity=severity,
                    narrative=narrative,
                    duration_seconds=duration,
                    first_seen=self._first_seen.get(obs_key, timestamp),
                    last_seen=timestamp,
                    evidence={'feature': feature, 'value': features.get(feature), 'zscore': zscore},
                    recommendations=["Investigate feature correlation", "Check for recent changes"]
                ))
        
        return anomalies
    
    def _calculate_zscores(self, features: Dict, baseline_stats: Optional[Dict]) -> Dict[str, float]:
        """Calculate z-scores for features."""
        if not baseline_stats:
            return {}
        
        zscores = {}
        for feature, value in features.items():
            if feature in baseline_stats:
                stats = baseline_stats[feature]
                mean = stats.get('mean', 0)
                std = stats.get('std', 1)
                if std > 0:
                    zscores[feature] = (value - mean) / std
        
        return zscores
    
    def _calculate_persistence(self, obs_key: str, timestamp: float) -> float:
        """Calculate how long this observation has persisted."""
        if obs_key not in self._first_seen:
            self._first_seen[obs_key] = timestamp
            return 0.0
        
        return timestamp - self._first_seen[obs_key]
    
    def _zscore_to_severity(self, zscore: float) -> SeverityLevel:
        """Map z-score to severity level."""
        if zscore >= self.ZSCORE_CRITICAL:
            return SeverityLevel.CRITICAL
        elif zscore >= self.ZSCORE_HIGH:
            return SeverityLevel.HIGH
        elif zscore >= self.ZSCORE_MEDIUM:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
    
    def _generate_memory_narrative(self, feature, value, zscore, duration) -> str:
        """Generate memory pressure narrative."""
        if 'available' in feature:
            base = f"Memory availability critically low"
        elif 'swap' in feature:
            base = f"System swapping to disk"
        else:
            base = f"Memory pressure elevated"
        
        # Add duration context
        if duration > self.PERSISTENCE_SYSTEMIC:
            temporal = f"for {self._format_duration(duration)} (systemic issue)"
        elif duration > self.PERSISTENCE_PERSISTENT:
            temporal = f"for {self._format_duration(duration)} (persistent problem)"
        elif duration > self.PERSISTENCE_SHORT:
            temporal = f"for {self._format_duration(duration)}"
        else:
            temporal = "(recent)"
        
        # Add magnitude
        magnitude = f"{abs(zscore):.1f}sigma above normal"
        
        return f"{base} {temporal} - {magnitude}"
    
    def _generate_io_narrative(self, feature, value, zscore, duration) -> str:
        """Generate I/O bottleneck narrative."""
        if 'p99' in feature:
            base = "I/O tail latency spike"
        elif 'p95' in feature:
            base = "I/O latency elevated"
        else:
            base = "I/O performance degraded"
        
        temporal = f"for {self._format_duration(duration)}" if duration > 60 else "(recent)"
        magnitude = f"{abs(zscore):.1f}sigma above baseline"
        
        return f"{base} {temporal} - {magnitude}"
    
    def _generate_cpu_narrative(self, feature, value, zscore, duration) -> str:
        """Generate CPU contention narrative."""
        if 'context_switch' in feature:
            base = "Excessive context switching detected"
        elif 'load' in feature:
            base = "CPU load significantly elevated"
        else:
            base = "CPU contention detected"
        
        temporal = f"for {self._format_duration(duration)}" if duration > 60 else "(recent)"
        magnitude = f"{abs(zscore):.1f}sigma above normal"
        
        return f"{base} {temporal} - {magnitude}"
    
    def _generate_network_narrative(self, feature, value, zscore, duration) -> str:
        """Generate network degradation narrative."""
        if 'error' in feature:
            base = "Network error rate spiking"
        elif 'drop' in feature:
            base = "Packet drops increasing"
        elif 'retrans' in feature:
            base = "TCP retransmissions elevated"
        else:
            base = "Network degradation detected"
        
        temporal = f"for {self._format_duration(duration)}" if duration > 60 else "(recent)"
        magnitude = f"{abs(zscore):.1f}sigma above baseline"
        
        return f"{base} {temporal} - {magnitude}"
    
    def reset_persistence(self, obs_key: Optional[str] = None):
        """
        Reset persistence tracking.
        
        Args:
            obs_key: Specific observation to reset, or None for all
        """
        if obs_key:
            self._first_seen.pop(obs_key, None)
        else:
            self._first_seen.clear()


# Example usage
if __name__ == '__main__':
    interpreter = SignalInterpreter()
    
    # Simulated feature values (from FeatureExporter)
    features = {
        'memory_available_pct': 5.2,  # Only 5% available!
        'swap_used_pct': 85.0,
        'io_read_latency_p95': 125.0,  # 125ms p95
        'load_1min': 8.5,
        'context_switch_rate': 15000
    }
    
    # Baseline statistics
    baseline_stats = {
        'memory_available_pct': {'mean': 45.0, 'std': 10.0},
        'swap_used_pct': {'mean': 5.0, 'std': 5.0},
        'io_read_latency_p95': {'mean': 8.0, 'std': 3.0},
        'load_1min': {'mean': 2.0, 'std': 1.0},
        'context_switch_rate': {'mean': 2000, 'std': 500}
    }
    
    # Interpret features
    observations = interpreter.interpret(features, baseline_stats)
    
    print(f"Generated {len(observations)} observations:\n")
    for obs in observations:
        print(f"[{obs.severity.value.upper()}] {obs.type.value}")
        print(f"  Narrative: {obs.narrative}")
        print(f"  Duration: {obs.duration_seconds:.0f}s")
        print(f"  Evidence: {obs.evidence.get('feature')} = {obs.evidence.get('value')}")
        print(f"  Recommendations:")
        for rec in obs.recommendations[:2]:  # Show first 2
            print(f"    - {rec}")
        print()

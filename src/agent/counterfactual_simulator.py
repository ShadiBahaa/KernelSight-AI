#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Counterfactual Simulator - Project future system states.

This module simulates "what-if" scenarios by extrapolating current trends
and comparing projected states against baselines to assess risk.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CounterfactualSimulator:
    """Simulates future system states for counterfactual reasoning."""
    
    def __init__(self):
        """Initialize simulator."""
        pass
    
    def simulate_pressure(self,
                         signal_type: str,
                         current_value: float,
                         trend_slope: float,
                         duration_minutes: int,
                         baselines: Optional[Dict] = None) -> Dict:
        """
        Simulate future pressure if current trend continues.
        
        Args:
            signal_type: e.g., 'memory_pressure'
            current_value: Current pressure score (0-1)
            trend_slope: Rate of change per minute
            duration_minutes: How far into future to project
            baselines: Optional baseline data for comparison
            
        Returns:
            Dict with simulation results:
            {
                'signal_type': 'memory_pressure',
                'current_value': 0.35,
                'projected_value': 0.65,
                'slope': 0.01,
                'duration_minutes': 30,
                'exceeds_baseline_at': 15,  # minutes (None if never)
                'reaches_critical_at': 25,  # minutes (None if never)
                'risk_level': 'high',
                'scenario_description': "...",
                'timeline': [...]  # List of checkpoints
            }
        """
        # Calculate projection
        projected_value = current_value + (trend_slope * duration_minutes)
        projected_value = max(0.0, min(1.0, projected_value))  # Clamp to [0, 1]
        
        # Get baseline thresholds if available
        baseline_p95 = None
        baseline_p99 = None
        if baselines and signal_type in baselines:
            nr = baselines[signal_type].get('normal_range', {})
            baseline_p95 = nr.get('p95')
            baseline_p99 = nr.get('p99')
        
        # Calculate threshold crossings
        exceeds_baseline_at = self._calculate_crossing_time(
            current_value, trend_slope, baseline_p95
        ) if baseline_p95 else None
        
        reaches_critical_at = self._calculate_crossing_time(
            current_value, trend_slope, 0.6  # 60% = critical threshold
        )
        
        # Assess risk level
        risk_level = self._assess_risk_level(
            current_value, projected_value, baseline_p95
        )
        
        # Generate scenario description
        scenario_description = self._generate_scenario_description(
            signal_type, current_value, projected_value, trend_slope, duration_minutes
        )
        
        # Build timeline
        timeline = self._build_timeline(
            current_value, trend_slope, duration_minutes,
            baseline_p95, baseline_p99
        )
        
        return {
            'signal_type': signal_type,
            'current_value': current_value,
            'projected_value': projected_value,
            'slope': trend_slope,
            'duration_minutes': duration_minutes,
            'exceeds_baseline_at': exceeds_baseline_at,
            'reaches_critical_at': reaches_critical_at,
            'risk_level': risk_level,
            'scenario_description': scenario_description,
            'timeline': timeline,
            'baseline_p95': baseline_p95
        }
    
    def _calculate_crossing_time(self,
                                 current: float,
                                 slope: float,
                                 threshold: Optional[float]) -> Optional[int]:
        """
        Calculate when value crosses threshold.
        
        Returns:
            Minutes until crossing, or None if never crosses
        """
        if threshold is None or slope <= 0:
            return None
        
        if current >= threshold:
            return 0  # Already exceeded
        
        minutes = (threshold - current) / slope
        
        if minutes < 0 or minutes > 10000:  # Unrealistic timeframe
            return None
        
        return int(minutes)
    
    def _assess_risk_level(self,
                          current: float,
                          projected: float,
                          baseline_p95: Optional[float]) -> str:
        """
        Assess risk level based on current and projected values.
        
        Returns:
            'low', 'medium', 'high', or 'critical'
        """
        # Critical: projected >= 60% (near system limits)
        if projected >= 0.6:
            return 'critical'
        
        # High: projected >= 45% OR well above baseline
        if projected >= 0.45:
            return 'high'
        
        if baseline_p95:
            if projected > baseline_p95 * 1.5:  # 50% above baseline
                return 'high'
            elif projected > baseline_p95 * 1.2:  # 20% above baseline
                return 'medium'
        
        # Medium: noticeable increase
        if projected > current * 1.3:
            return 'medium'
        
        return 'low'
    
    def _generate_scenario_description(self,
                                      signal_type: str,
                                      current: float,
                                      projected: float,
                                      slope: float,
                                      duration: int) -> str:
        """Generate natural language scenario description."""
        metric_name = signal_type.replace('_', ' ').title()
        
        if slope > 0.001:
            trend = "rising steadily"
        elif slope > 0:
            trend = "increasing slightly"
        else:
            trend = "stable"
        
        change_pct = ((projected - current) / current * 100) if current > 0 else 0
        
        desc = (
            f"{metric_name} is currently {current:.1%}, {trend} at "
            f"{slope:.4f} per minute. If this trend continues for {duration} minutes, "
            f"pressure will reach {projected:.1%} ({change_pct:+.1f}% change)."
        )
        
        return desc
    
    def _build_timeline(self,
                       current: float,
                       slope: float,
                       duration: int,
                       baseline_p95: Optional[float],
                       baseline_p99: Optional[float]) -> list:
        """
        Build timeline of checkpoints showing progression.
        
        Returns:
            List of checkpoint dicts with time and status
        """
        timeline = []
        
        # Add current state
        timeline.append({
            'time_minutes': 0,
            'value': current,
            'status': 'Current state'
        })
        
        # Add baseline threshold crossings
        if baseline_p95:
            crossing_time = self._calculate_crossing_time(current, slope, baseline_p95)
            if crossing_time and 0 < crossing_time <= duration:
                projected_at_crossing = current + (slope * crossing_time)
                timeline.append({
                    'time_minutes': crossing_time,
                    'value': projected_at_crossing,
                    'status': f'Exceeds baseline p95 ({baseline_p95:.2f})'
                })
        
        if baseline_p99:
            crossing_time = self._calculate_crossing_time(current, slope, baseline_p99)
            if crossing_time and 0 < crossing_time <= duration:
                projected_at_crossing = current + (slope * crossing_time)
                timeline.append({
                    'time_minutes': crossing_time,
                    'value': projected_at_crossing,
                    'status': f'Exceeds baseline p99 ({baseline_p99:.2f})'
                })
        
        # Add critical threshold
        critical_time = self._calculate_crossing_time(current, slope, 0.6)
        if critical_time and 0 < critical_time <= duration:
            timeline.append({
                'time_minutes': critical_time,
                'value': 0.6,
                'status': 'CRITICAL threshold (60%)'
            })
        
        # Add final projection
        final_value = current + (slope * duration)
        final_value = max(0.0, min(1.0, final_value))
        timeline.append({
            'time_minutes': duration,
            'value': final_value,
            'status': 'Projected end state'
        })
        
        # Sort by time
        timeline.sort(key=lambda x: x['time_minutes'])
        
        return timeline


if __name__ == "__main__":
    # Test counterfactual simulator
    simulator = CounterfactualSimulator()
    
    # Test scenario: Memory pressure increasing
    print("\n=== Counterfactual Simulation: Memory Pressure ===\n")
    
    mock_baselines = {
        'memory_pressure': {
            'normal_range': {
                'median': 0.22,
                'p95': 0.27,
                'p99': 0.35
            }
        }
    }
    
    result = simulator.simulate_pressure(
        signal_type='memory_pressure',
        current_value=0.35,
        trend_slope=0.01,  # 1% per minute
        duration_minutes=30,
        baselines=mock_baselines
    )
    
    print(f"Scenario: {result['scenario_description']}\n")
    print(f"Risk Level: {result['risk_level'].upper()}")
    print(f"Exceeds baseline in: {result['exceeds_baseline_at']} minutes" if result['exceeds_baseline_at'] else "Within baseline")
    print(f"Reaches critical in: {result['reaches_critical_at']} minutes\n" if result['reaches_critical_at'] else "Won't reach critical\n")
    
    print("Timeline:")
    for checkpoint in result['timeline']:
        minutes = checkpoint['time_minutes']
        value = checkpoint['value']
        status = checkpoint['status']
        print(f"  [+{minutes:2d}m] {value:.1%} - {status}")

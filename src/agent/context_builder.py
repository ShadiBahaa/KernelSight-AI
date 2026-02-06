#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Context Builder - Format baselines and signals for Gemini 3 reasoning.

This module takes system baselines and current signals, then formats them
into a structured context that Gemini 3 can use for autonomous reasoning.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds structured context for Gemini 3 from baselines and signals."""
    
    def __init__(self):
        """Initialize context builder."""
        pass
    
    def build_signal_context(self, 
                            current_signals: List[Dict],
                            baselines: Dict,
                            analysis_goal: str = "diagnose") -> str:
        """
        Build context prompt for Gemini 3 analysis.
        
        Args:
            current_signals: List of recent signals from signal_metadata
            baselines: Dict from baseline_analyzer.load_baselines()
            analysis_goal: Type of analysis ('diagnose', 'predict', 'recommend')
            
        Returns:
            Formatted context string for Gemini 3 prompt
        """
        context_parts = []
        
        # 1. System baseline knowledge
        context_parts.append(self._format_baseline_section(baselines))
        
        # 2. Current observations
        context_parts.append(self._format_current_signals(current_signals, baselines))
        
       # 3. Analysis task
        context_parts.append(self._format_analysis_task(analysis_goal))
        
        return "\n\n".join(context_parts)
    
    def _format_baseline_section(self, baselines: Dict) -> str:
        """Format baseline knowledge section."""
        if not baselines:
            return "SYSTEM BASELINE KNOWLEDGE:\nNo baseline data available (system recently deployed)."
        
        lines = ["SYSTEM BASELINE KNOWLEDGE:"]
        lines.append("The following represents normal system behavior based on recent history:\n")
        
        for signal_type, baseline in sorted(baselines.items()):
            metric_name = signal_type.replace('_', ' ').title()
            
            # Range
            if baseline.get('normal_range'):
                nr = baseline['normal_range']
                lines.append(
                    f"- {metric_name}: Normally {nr['min']:.2f} to {nr['max']:.2f} "
                    f"(median {nr['median']:.2f}, p95 {nr['p95']:.2f})"
                )
            
            # Pattern and volatility
            pattern = baseline.get('temporal_pattern', 'unknown')
            volatility = baseline.get('volatility', 'unknown')
            if pattern not in ('unknown', 'insufficient_data'):
                lines.append(f"  • Occurs with {pattern} pattern, {volatility} volatility")
            
            # Trend
            trend = baseline.get('trend', 'unknown')
            if trend != 'unknown':
                lines.append(f"  • Recent trend: {trend}")
        
        return "\n".join(lines)
    
    def _format_current_signals(self, signals: List[Dict], baselines: Dict) -> str:
        """Format current signal observations with deviation analysis."""
        if not signals:
            return "CURRENT OBSERVATIONS:\nNo recent signals (system appears healthy)."
        
        lines = ["CURRENT OBSERVATIONS:"]
        lines.append(f"Analyzed {len(signals)} recent signal(s):\n")
        
        # Group by signal type
        by_type = {}
        for signal in signals:
            sig_type = signal['signal_type']
            if sig_type not in by_type:
                by_type[sig_type] = []
            by_type[sig_type].append(signal)
        
        # Format each type
        for signal_type, type_signals in sorted(by_type.items()):
            latest = type_signals[0]  # Most recent
            count = len(type_signals)
            
            metric_name = signal_type.replace('_', ' ').title()
            severity = latest.get('severity', 'unknown')
            pressure = latest.get('pressure_score', 0.0)
            summary = latest.get('summary', 'No summary available')
            
            # Compare to baseline
            deviation_note = self._calculate_deviation(signal_type, pressure, baselines)
            
            lines.append(f"• {metric_name}:")
            lines.append(f"  - Severity: {severity}, Pressure: {pressure:.2f}")
            lines.append(f"  - Summary: {summary}")
            if deviation_note:
                lines.append(f"  - Baseline: {deviation_note}")
            if count > 1:
                lines.append(f"  - Frequency: {count} occurrence(s) in this window")
        
        return "\n".join(lines)
    
    def _calculate_deviation(self, signal_type: str, current_value: float, 
                            baselines: Dict) -> Optional[str]:
        """Calculate how current value deviates from baseline."""
        baseline = baselines.get(signal_type)
        if not baseline or not baseline.get('normal_range'):
            return None
        
        nr = baseline['normal_range']
        median = nr['median']
        p95 = nr['p95']
        
        if current_value < nr['min']:
            return f"BELOW normal range (min: {nr['min']:.2f})"
        elif current_value <= median:
            return f"WITHIN normal range (at median)"
        elif current_value <= p95:
            return f"ELEVATED but within p95 ({p95:.2f})"
        else:
            deviation_pct = ((current_value - p95) / p95) * 100
            return f"ABOVE p95 by {deviation_pct:.1f}%"
    
    def _format_analysis_task(self, analysis_goal: str) -> str:
        """Format the analysis task for Gemini 3."""
        if analysis_goal == "diagnose":
            return """TASK: Root Cause Analysis
Analyze the current observations relative to the baseline. Identify:
1. Which metrics deviate significantly from normal behavior
2. Possible root causes for these deviations
3. Relationships between different pressure signals (e.g., high load + memory pressure)
4. Recommended investigation steps"""
        
        elif analysis_goal == "predict":
            return """TASK: Predictive Analysis
Based on current signals and trends:
1. Predict which metrics are likely to worsen in the near term
2. Estimate time-to-failure if current trends continue
3. Identify early warning signs of impending issues
4. Suggest proactive remediation actions"""
        
        elif analysis_goal == "recommend":
            return """TASK: Remediation Recommendations
Provide actionable recommendations to resolve current issues:
1. Safe actions that can be taken immediately
2. Actions requiring human approval
3. Long-term fixes to prevent recurrence
4. Monitoring steps to validate effectiveness"""
        
        else:
            return f"""TASK: {analysis_goal}
Analyze the system state and provide insights based on the observations."""
    
    def build_correlation_context(self, signal_pairs: List[Tuple[Dict, Dict]]) -> str:
        """
        Build context for analyzing signal correlations.
        
        Args:
            signal_pairs: List of (signal1, signal2) tuples to analyze
            
        Returns:
            Formatted context for correlation analysis
        """
        if not signal_pairs:
            return "No correlated signals to analyze."
        
        lines = ["CORRELATED SIGNAL ANALYSIS:"]
        lines.append(f"Found {len(signal_pairs)} potentially related signal pair(s):\n")
        
        for i, (sig1, sig2) in enumerate(signal_pairs, 1):
            time_delta = abs(sig1['timestamp'] - sig2['timestamp']) / 1_000_000_000  # to seconds
            
            lines.append(f"{i}. {sig1['signal_type']} ↔ {sig2['signal_type']}")
            lines.append(f"   Time separation: {time_delta:.2f} seconds")
            lines.append(f"   Signal 1: {sig1.get('summary', 'N/A')}")
            lines.append(f"   Signal 2: {sig2.get('summary', 'N/A')}")
            lines.append("")
        
        lines.append("TASK: Determine if these signals represent:")
        lines.append("1. Causal relationship (one caused the other)")
        lines.append("2. Common root cause (both caused by same issue)")
        lines.append("3. Coincidence (unrelated)")
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Test context builder
    builder = ContextBuilder()
    
    # Mock baseline data
    baselines = {
        "memory_pressure": {
            "normal_range": {"min": 0.16, "max": 0.45, "median": 0.22, "p95": 0.27},
            "volatility": "low",
            "temporal_pattern": "burst",
            "trend": "stable"
        },
        "load_mismatch": {
            "normal_range": {"min": 0.25, "max": 0.28, "median": 0.26, "p95": 0.28},
            "volatility": "low",
            "temporal_pattern": "burst",
            "trend": "stable"
        }
    }
    
    # Mock signals
    current_signals = [
        {
            "signal_type": "memory_pressure",
            "severity": "high",
            "pressure_score": 0.35,
            "summary": "Memory pressure: Only 65% available (high utilization)",
            "timestamp": 1704902400000000000
        },
        {
            "signal_type": "load_mismatch",
            "severity": "high",
            "pressure_score": 0.45,
            "summary": "CPU load: 1.8x cores (above expected)",
            "timestamp": 1704902400000000000
        }
    ]
    
    # Build context
    context = builder.build_signal_context(current_signals, baselines, "diagnose")
    
    print("="*70)
    print("GEMINI 3 CONTEXT EXAMPLE")
    print("="*70)
    print(context)
    print("="*70)

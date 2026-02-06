#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Counterfactual Prompts - Gemini 3 prompt templates for forward reasoning.

This module contains prompt templates that enable Gemini 3 to reason about
future system states, cascading effects, and risk escalation through
counterfactual "what-if" scenarios.
"""

from typing import Dict, List


def build_forward_projection_prompt(simulation: Dict, baselines: Dict = None) -> str:
    """
    Build prompt for forward projection reasoning.
    
    Args:
        simulation: Output from CounterfactualSimulator.simulate_pressure()
        baselines: Optional baseline data for context
        
    Returns:
        Formatted prompt string for Gemini 3
    """
    signal_type = simulation['signal_type']
    metric_name = signal_type.replace('_', ' ').title()
    
    # Build baseline context if available
    baseline_context = ""
    if baselines and signal_type in baselines:
        nr = baselines[signal_type].get('normal_range', {})
        baseline_context = f"""
BASELINE KNOWLEDGE:
- Normal {metric_name}: {nr.get('min', 0):.2f} to {nr.get('max', 1):.2f}
- Typical (median): {nr.get('median', 0):.2f}
- Upper threshold (p95): {nr.get('p95', 0):.2f}
"""
    
    # Build timeline section
    timeline_str = "\n".join([
        f"  [+{cp['time_minutes']:2d} min] {cp['value']:.1%} - {cp['status']}"
        for cp in simulation['timeline']
    ])
    
    prompt = f"""
SYSTEM STATE ANALYSIS

CURRENT OBSERVATION:
- {metric_name}: {simulation['current_value']:.1%}
- Trend: {simulation['slope']:+.4f} per minute ({'increasing' if simulation['slope'] > 0 else 'stable'})
{baseline_context}

COUNTERFACTUAL SCENARIO:
"If {metric_name} continues at current rate for {simulation['duration_minutes']} minutes..."

PROJECTED OUTCOME:
- Final state: {simulation['projected_value']:.1%}
- Risk level: {simulation['risk_level'].upper()}
- Time to reach critical (60%): {simulation['reaches_critical_at'] or 'N/A'} minutes

PROGRESSION TIMELINE:
{timeline_str}

REASONING TASKS:

1. **Failure Mode Analysis**
   What specific failure modes become likely at {simulation['projected_value']:.0%} {metric_name.lower()}?
   Consider:
   - Service degradation symptoms
   - Cascading resource exhaustion
   - System protection mechanisms (OOM killer, swap, etc.)

2. **Cascading Effects**
   If {metric_name.lower()} reaches {simulation['projected_value']:.0%}, which other system metrics will be affected?
   Trace the causal chain:
   - Direct consequences (e.g., memory → swap activation)
   - Secondary effects (e.g., swap → I/O  congestion)
   - Tertiary impacts (e.g., I/O → service latency)

3. **Time-to-Failure Estimation**
   Based on the timeline above, when does the system become:
   - Degraded (noticeable slowdown)
   - Critical (service failures begin)
   - Failed (complete outage or crash)

4. **Preventive Actions**
   What actions should be taken, and when?
   - IMMEDIATE (within 5 minutes)
   - SHORT-TERM (5-15 minutes)
   - MEDIUM-TERM (15-30 minutes)

Provide a structured narrative with time estimates and causal explanations.
"""
    
    return prompt.strip()


def build_cascading_effects_prompt(primary_signal: Dict,
                                  related_signals: List[Dict]) -> str:
    """
    Build prompt for cascading effects analysis.
    
    Args:
        primary_signal: The initial pressure signal
        related_signals: Other signals that may be affected
        
    Returns:
        Formatted prompt for cascade reasoning
    """
    primary_type = primary_signal['signal_type']
    primary_name = primary_type.replace('_', ' ').title()
    
    # Format related signals
    related_str = "\n".join([
        f"- {sig['signal_type']}: {sig.get('current_value', 0):.1%} "
        f"({sig.get('severity', 'unknown')} severity)"
        for sig in related_signals
    ])
    
    prompt = f"""
CASCADING FAILURE ANALYSIS

PRIMARY PRESSURE:
- {primary_name}: {primary_signal.get('current_value', 0):.1%}
- Trend: {primary_signal.get('trend_direction', 'unknown')}
- Summary: {primary_signal.get('summary', 'No summary available')}

RELATED SYSTEM METRICS:
{related_str}

COUNTERFACTUAL SCENARIO:
"If {primary_name.lower()} continues degrading and reaches critical levels..."

REASONING TASKS:

1. **Identify Causal Chain**
   Map the cascade of effects:
   - What does {primary_name.lower()} directly impact?
   - Which metrics worsen as a consequence?
   - What is the propagation timeline?

2. **Predict Secondary Failures**
   Which services or processes fail first?
   - Most vulnerable components
   - Breaking points in the dependency chain
   - Expected symptoms users will observe

3. **Assess Cascade Severity**
   Rate the cascade potential:
   - Contained (affects only one subsystem)
   - Spreading (multiple subsystems)
   - Systemic (total system failure)

4. **Breaking the Cascade**
   What interventions stop the cascade?
   - Which link in the chain to break
   - Timing requirements
   - Trade-offs of each action

Explain the causal relationships and cascade dynamics.
"""
    
    return prompt.strip()


def build_risk_escalation_prompt(current_state: List[Dict],
                                 projected_state: List[Dict],
                                 duration_minutes: int) -> str:
    """
    Build prompt for risk escalation timeline.
    
    Args:
        current_state: List of current signals
        projected_state: List of projected signals
        duration_minutes: Projection timeframe
        
    Returns:
        Formatted prompt for risk assessment
    """
    # Format current state
    current_str = "\n".join([
        f"- {sig['signal_type']}: {sig.get('current_value', 0):.1%} "
        f"({sig.get('severity', 'unknown')})"
        for sig in current_state
    ])
    
    # Format projected state
    projected_str = "\n".join([
        f"- {sig['signal_type']}: {sig.get('projected_value', 0):.1%} "
        f"({sig.get('risk_level', 'unknown')})"
        for sig in projected_state
    ])
    
    prompt = f"""
RISK ESCALATION ASSESSMENT

CURRENT STATE (T=0):
{current_str}

PROJECTED STATE (T+{duration_minutes} minutes):
{projected_str}

COMPARATIVE ANALYSIS TASK:

1. **Risk Level Changes**
   For each metric, analyze:
   - Current severity → Projected severity
   - Is this an escalation, de-escalation, or stable?
   - Which metrics show the most concerning changes?

2. **New Failure Modes**
   What failures become possible in projected state that aren't risks now?
   - Memory exhaustion → OOM killer
   - I/O saturation → service timeout
   - Network degradation → connection drops

3. **Point of No Return**
   Is there a critical moment before T+{duration_minutes} where intervention becomes impossible?
   - When does degradation become irreversible?
   - What are the early warning signs?
   - How much reaction time do we have?

4. **Alert Strategy**
   What monitoring alerts should trigger, and when?
   - WARNING (early detection)
   - CRITICAL (immediate action required)
   - EMERGENCY (system failure imminent)

Provide a timeline of risk escalation with intervention opportunities.
"""
    
    return prompt.strip()


if __name__ == "__main__":
    # Test prompt generation
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    from agent.counterfactual_simulator import CounterfactualSimulator
    
    simulator = CounterfactualSimulator()
    
    # Simulate a scenario
    simulation = simulator.simulate_pressure(
        signal_type='memory_pressure',
        current_value=0.35,
        trend_slope=0.01,
        duration_minutes=30,
        baselines={
            'memory_pressure': {
                'normal_range': {
                    'min': 0.16,
                    'max': 0.45,
                    'median': 0.22,
                    'p95': 0.27,
                    'p99': 0.35
                }
            }
        }
    )
    
    # Generate prompt
    prompt = build_forward_projection_prompt(
        simulation,
        baselines={
            'memory_pressure': {
                'normal_range': {
                    'min': 0.16,
                    'max': 0.45,
                    'median': 0.22,
                    'p95': 0.27
                }
            }
        }
    )
    
    print("=" * 80)
    print("GEMINI 3 COUNTERFACTUAL PROMPT")
    print("=" * 80)
    print(prompt)
    print("=" * 80)

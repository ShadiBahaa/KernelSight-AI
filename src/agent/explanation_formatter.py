#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Explanation Formatter - Day 12: Human-Readable Causal Chains.

Converts structured reasoning → plain language explanations.

Output is:
- Human-readable (non-technical audience)
- Causal (A → B → C chains)
- Transparent (explicit uncertainty)
- Judge-friendly (presentation-ready)
"""

from typing import Dict, List, Optional
from agent.reasoning_templates import StructuredReasoning


def format_causal_explanation(reasoning: StructuredReasoning, 
                              format_type: str = "full") -> str:
    """
    Convert structured reasoning to human-readable explanation.
    
    Args:
        reasoning: StructuredReasoning instance
        format_type: "full", "summary", or "markdown"
        
    Returns:
        Formatted explanation string
    """
    if format_type == "summary":
        return _format_summary(reasoning)
    elif format_type == "markdown":
        return _format_markdown(reasoning)
    else:
        return _format_full(reasoning)


def _format_full(reasoning: StructuredReasoning) -> str:
    """Full detailed explanation."""
    
    sections = []
    
    # Header
    sections.append("=" * 70)
    sections.append("AUTONOMOUS AGENT REASONING REPORT")
    sections.append(f"Timestamp: {reasoning.timestamp}")
    sections.append(f"Overall Confidence: {reasoning.confidence * 100:.0f}%")
    sections.append("=" * 70)
    sections.append("")
    
    # Observation
    sections.append("📊 OBSERVATION")
    sections.append("-" * 70)
    sections.append(reasoning.observation)
    if reasoning.signal_citations:
        sections.append("\nSignal References:")
        for sig in reasoning.signal_citations:
            sections.append(f"  - Signal #{sig.get('id')}: {sig.get('type')} at {sig.get('timestamp')}")
    sections.append("")
    
    # Hypothesis
    sections.append("💡 HYPOTHESIS (Causal Claim)")
    sections.append("-" * 70)
    sections.append(reasoning.hypothesis)
    sections.append("")
    
    # Evidence
    sections.append("📈 EVIDENCE (Quantified Facts)")
    sections.append("-" * 70)
    for i, ev in enumerate(reasoning.evidence, 1):
        sections.append(f"{i}. {ev}")
    sections.append("")
    
    # Baseline Context
    sections.append("📏 BASELINE CONTEXT")
    sections.append("-" * 70)
    sections.append(reasoning.baseline_context)
    sections.append("")
    
    # Predicted Outcome
    sections.append("⚠️  PREDICTED OUTCOME (If No Action)")
    sections.append("-" * 70)
    sections.append(reasoning.predicted_outcome)
    sections.append("")
    
    # Recommended Action
    sections.append("🔧 RECOMMENDED ACTION")
    sections.append("-" * 70)
    action = reasoning.recommended_action
    sections.append(f"Action Type: {action.get('action_type')}")
    sections.append(f"Parameters: {action.get('params', {})}")
    sections.append(f"Command: {action.get('command', 'N/A')}")
    sections.append(f"Expected Effect: {action.get('expected_effect', 'N/A')}")
    sections.append("")
    
    # Risks & Rollback
    sections.append("⚖️  RISKS & ROLLBACK PLAN")
    sections.append("-" * 70)
    risks = reasoning.risks_and_rollback
    sections.append("Risks:")
    for risk in risks.get('risks', []):
        sections.append(f"  - {risk}")
    sections.append(f"\nBlast Radius: {risks.get('blast_radius', 'unknown')}")
    sections.append(f"Reversible: {'Yes' if risks.get('reversible') else 'No'}")
    sections.append(f"Rollback: {risks.get('rollback_command', 'N/A')}")
    sections.append("")
    
    # Confidence Breakdown
    sections.append("🎯 CONFIDENCE ASSESSMENT")
    sections.append("-" * 70)
    sections.append(f"Overall Confidence: {reasoning.confidence * 100:.0f}%")
    if reasoning.uncertainty_sources:
        sections.append("\nUncertainty Sources:")
        for source in reasoning.uncertainty_sources:
            sections.append(f"  - {source}")
    sections.append("")
    
    sections.append("=" * 70)
    
    return "\n".join(sections)


def _format_summary(reasoning: StructuredReasoning) -> str:
    """Concise one-paragraph summary."""
    
    return (
        f"[{reasoning.confidence * 100:.0f}% confidence] "
        f"{reasoning.observation.split('.')[0]}. "
        f"{reasoning.hypothesis}. "
        f"Recommendation: {reasoning.recommended_action.get('action_type')} "
        f"({reasoning.risks_and_rollback.get('blast_radius', 'unknown')} impact, "
        f"{'reversible' if reasoning.risks_and_rollback.get('reversible') else 'irreversible'})."
    )


def _format_markdown(reasoning: StructuredReasoning) -> str:
    """Markdown format for documentation/reports."""
    
    md = []
    
    md.append("# Autonomous Agent Reasoning Report\n")
    md.append(f"**Timestamp**: {reasoning.timestamp}  ")
    md.append(f"**Confidence**: {reasoning.confidence * 100:.0f}%\n")
    md.append("---\n")
    
    md.append("## 📊 Observation\n")
    md.append(f"{reasoning.observation}\n")
    
    md.append("## 💡 Hypothesis\n")
    md.append(f"{reasoning.hypothesis}\n")
    
    md.append("## 📈 Evidence\n")
    for ev in reasoning.evidence:
        md.append(f"- {ev}")
    md.append("")
    
    md.append("## 📏 Baseline Context\n")
    md.append(f"{reasoning.baseline_context}\n")
    
    md.append("## ⚠️ Predicted Outcome\n")
    md.append(f"{reasoning.predicted_outcome}\n")
    
    md.append("## 🔧 Recommended Action\n")
    action = reasoning.recommended_action
    md.append(f"- **Action**: `{action.get('action_type')}`")
    md.append(f"- **Parameters**: `{action.get('params', {})}`")
    md.append(f"- **Command**: `{action.get('command', 'N/A')}`")
    md.append(f"- **Expected Effect**: {action.get('expected_effect', 'N/A')}\n")
    
    md.append("## ⚖️ Risks & Rollback\n")
    risks = reasoning.risks_and_rollback
    md.append("**Risks**:")
    for risk in risks.get('risks', []):
        md.append(f"- {risk}")
    md.append(f"\n**Blast Radius**: {risks.get('blast_radius')}")
    md.append(f"**Reversible**: {'Yes' if risks.get('reversible') else 'No'}")
    md.append(f"**Rollback**: `{risks.get('rollback_command', 'N/A')}`\n")
    
    md.append("## 🎯 Confidence\n")
    md.append(f"**Overall**: {reasoning.confidence * 100:.0f}%\n")
    if reasoning.uncertainty_sources:
        md.append("**Uncertainty Sources**:")
        for source in reasoning.uncertainty_sources:
            md.append(f"- {source}")
    
    return "\n".join(md)


def format_causal_chain(reasoning: StructuredReasoning) -> str:
    """
    Extract explicit causal chain: A → B → C
    
    Example:
    "Process leak → Memory accumulation → OOM risk → Service disruption"
    """
    # Extract causal elements from hypothesis and outcome
    elements = []
    
    # Parse hypothesis for cause
    if '->' in reasoning.hypothesis or '→' in reasoning.hypothesis:
        # Already has causal chain
        return reasoning.hypothesis
    
    # Build chain from components
    elements.append(_extract_root_cause(reasoning.hypothesis))
    elements.append(_extract_mechanism(reasoning.evidence))
    elements.append(_extract_impact(reasoning.predicted_outcome))
    
    return " → ".join(elements)


def _extract_root_cause(hypothesis: str) -> str:
    """Extract root cause from hypothesis."""
    # Simple extraction - first clause
    if ' causing ' in hypothesis:
        return hypothesis.split(' causing ')[0]
    if ' has ' in hypothesis:
        return hypothesis.split(' has ')[0] + ' issue'
    return "Root cause"


def _extract_mechanism(evidence: List[str]) -> str:
    """Extract mechanism from evidence."""
    for ev in evidence:
        if 'trend' in ev.lower() or 'increase' in ev.lower():
            return "Progressive degradation"
    return "System degradation"


def _extract_impact(outcome: str) -> str:
    """Extract impact from predicted outcome."""
    if 'OOM' in outcome:
        return "OOM risk"
    if 'crash' in outcome.lower():
        return "System crash"
    if 'disruption' in outcome.lower():
        return "Service disruption"
    return "System impact"


if __name__ == "__main__":
    from reasoning_templates import create_reasoning_structure
    
    print("=== Explanation Formatter Test ===\n")
    
    # Create sample reasoning
    reasoning = create_reasoning_structure(
        observation="Memory pressure at 35% (signal #1234, 10:45 AM). Baseline p95: 27%. Deviation: +29.6%",
        hypothesis="Process 5678 (python app.py) has a memory leak causing gradual accumulation",
        evidence=[
            "Trend: +1.2% per minute over 30 minutes",
            "Statistical confidence: 92% (r²=0.92)",
            "Pattern: Gradual increase, not spike",
            "Process RSS: 800MB → 1.2GB in 2 hours"
        ],
        baseline_context="Current 35% vs baseline p95 27% → +29.6% deviation",
        predicted_outcome="System will reach OOM threshold (60%) in approximately 25 minutes. Risk level: CRITICAL. Cascade: OOM killer → service disruption",
        recommended_action={
            "action_type": "lower_process_priority",
            "params": {"pid": 5678, "priority": 10},
            "command": "renice +10 -p 5678",
            "expected_effect": "Reduce memory consumption by 20-30%"
        },
        risks_and_rollback={
            "risks": ["Process may become slower", "May timeout on requests"],
            "blast_radius": "single_process",
            "reversible": True,
            "rollback_command": "renice -10 -p 5678"
        },
        confidence=0.85,
        uncertainty_sources=["Limited historical data for this process"]
    )
    
    # Test full format
    print("=== FULL FORMAT ===\n")
    print(format_causal_explanation(reasoning, "full"))
    
    print("\n\n=== SUMMARY FORMAT ===\n")
    print(format_causal_explanation(reasoning, "summary"))
    
    print("\n\n=== CAUSAL CHAIN ===\n")
    print(format_causal_chain(reasoning))

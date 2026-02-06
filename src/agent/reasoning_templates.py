#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Structured Reasoning Templates - Day 12: Trust & Transparency Layer.

Enforces structured format for agent reasoning:
1. Observation (cite signals)
2. Hypothesis (causal claim)
3. Evidence (quantified)
4. Baseline Context
5. Predicted Outcome
6. Recommended Action
7. Risks & Rollback
8. Confidence (0.0-1.0)

No hallucinated certainty. Every claim must be grounded in data.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StructuredReasoning:
    """
    Enforced structure for agent reasoning.
    
    This makes AI decisions transparent and judge-friendly.
    """
    # Required fields
    observation: str  # What did I observe? (cite specific signals)
    hypothesis: str  # What do I think is happening? (causal claim)
    evidence: List[str]  # What supports this? (quantified facts)
    baseline_context: str  # How does this compare to normal?
    predicted_outcome: str  # What happens if I do nothing?
    recommended_action: Dict[str, Any]  # What should I do? (structured)
    risks_and_rollback: Dict[str, Any]  # What could go wrong? How to undo?
    confidence: float  # How sure am I? (0.0-1.0)
    
    # Optional fields
    signal_citations: List[Dict] = None  # Specific signals referenced
    uncertainty_sources: List[str] = None  # Known unknowns
    timestamp: str = None  # When was this reasoning performed


# Template for observation
OBSERVATION_TEMPLATE = """
What anomaly did I detect?

Requirements:
- Cite specific signal ID and timestamp
- Include current value
- Compare to baseline
- State deviation percentage

Example:
"Memory pressure at 35% (signal #1234, 10:45 AM). Baseline p95: 27%. Deviation: +29.6% above normal."

BAD (vague): "Memory is high"
GOOD (specific): "Memory at 35% (signal #1234, baseline: 27%, +29.6%)"
"""

# Template for hypothesis
HYPOTHESIS_TEMPLATE = """
What causal mechanism explains this?

Requirements:
- State the suspected root cause
- Be specific (process ID, subsystem, etc.)
- Use causal language (X causes Y)

Example:
"Process 5678 (python app.py) has a memory leak causing gradual accumulation"

BAD (vague): "Something is using memory"
GOOD (causal): "Process 5678 leak → memory accumulation → OOM risk"
"""

# Template for evidence
EVIDENCE_TEMPLATE = """
What quantified facts support this hypothesis?

Requirements:
- Include trend data (slope, direction)
- Statistical confidence (r², sample count)
- Pattern description
- Time-series evidence

Example:
1. Trend: +1.2% per minute over 30 minutes
2. Confidence: 92% (r²=0.92)
3. Pattern: Gradual increase, not spike
4. Process RSS grew from 800MB → 1.2GB in 2 hours

BAD (vague): "It's been increasing"
GOOD (quantified): "+1.2%/min, r²=0.92, 2hr accumulation"
"""

# Template for predicted outcome
OUTCOME_TEMPLATE = """
What happens if no action is taken?

Requirements:
- Time to critical threshold
- Risk level assessment
- Potential cascade effects
- Business impact

Example:
"System will reach OOM threshold (60%) in approximately 25 minutes.
Risk level: CRITICAL
Cascade: May trigger OOM killer → service disruption → user impact"

BAD (vague): "Things will get worse"
GOOD (specific): "OOM in 25min → service down → user impact"
"""

# Template for recommended action
ACTION_TEMPLATE = """
What structured action should be taken?

Requirements:
- Action type (from catalog)
- Parameters with values
- Actual command that will run
- Expected effect

Example:
{
    "action_type": "lower_process_priority",
    "params": {"pid": 5678, "priority": 10},
    "command": "renice +10 -p 5678",
    "expected_effect": "Reduce memory consumption by 20-30%"
}

BAD (vague): "Fix the memory issue"
GOOD (structured): Action type + params + expected effect
"""

# Template for risks
RISK_TEMPLATE = """
What are the risks and how to rollback?

Requirements:
- List specific risks
- Blast radius (what's affected)
- Reversibility (can we undo?)
- Rollback command

Example:
{
    "risks": ["Process becomes slower", "May timeout on requests"],
    "blast_radius": "single_process",
    "reversible": true,
    "rollback_command": "renice -10 -p 5678"
}

BAD (vague): "Might have issues"
GOOD (specific): Risks + blast radius + rollback plan
"""


def create_reasoning_structure(
    observation: str,
    hypothesis: str,
    evidence: List[str],
    baseline_context: str,
    predicted_outcome: str,
    recommended_action: Dict,
    risks_and_rollback: Dict,
    confidence: float,
    signal_citations: Optional[List[Dict]] = None,
    uncertainty_sources: Optional[List[str]] = None
) -> StructuredReasoning:
    """
    Create validated structured reasoning.
    
    Args:
        All fields from StructuredReasoning dataclass
        
    Returns:
        StructuredReasoning instance
        
    Raises:
        ValueError: If required fields missing or invalid
    """
    # Validate confidence
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")
    
    # Validate observation cites signals
    if not signal_citations and '#' not in observation:
        raise ValueError("Observation must cite specific signal IDs (e.g., signal #1234)")
    
    # Validate evidence is quantified
    if not evidence:
        raise ValueError("Evidence cannot be empty")
    
    # Check for hallucinated certainty
    forbidden_phrases = ['definitely', 'certainly', 'guaranteed', 'will 100%']
    for phrase in forbidden_phrases:
        if phrase.lower() in hypothesis.lower():
            raise ValueError(f"No hallucinated certainty allowed: '{phrase}'")
    
    return StructuredReasoning(
        observation=observation,
        hypothesis=hypothesis,
        evidence=evidence,
        baseline_context=baseline_context,
        predicted_outcome=predicted_outcome,
        recommended_action=recommended_action,
        risks_and_rollback=risks_and_rollback,
        confidence=confidence,
        signal_citations=signal_citations or [],
        uncertainty_sources=uncertainty_sources or [],
        timestamp=datetime.now().isoformat()
    )


def validate_reasoning_completeness(reasoning: StructuredReasoning) -> Dict:
    """
    Validate all required fields are meaningful.
    
    Returns:
        {
            'valid': True/False,
            'missing': [...],
            'warnings': [...]
        }
    """
    issues = []
    warnings = []
    
    # Check non-empty
    if len(reasoning.observation) < 20:
        issues.append("Observation too brief (min 20 chars)")
    
    if len(reasoning.hypothesis) < 15:
        issues.append("Hypothesis too brief (min 15 chars)")
    
    if not reasoning.evidence:
        issues.append("Evidence cannot be empty")
    
    # Check confidence is explicit
    if reasoning.confidence == 0.0:
        warnings.append("Confidence is 0.0 - is this intentional?")
    
    # Check for vague language
    vague_terms = ['maybe', 'possibly', 'might be', 'could be']
    for term in vague_terms:
        if term in reasoning.hypothesis.lower():
            warnings.append(f"Vague language detected: '{term}' - quantify uncertainty via confidence score instead")
    
    return {
        'valid': len(issues) == 0,
        'missing': issues,
        'warnings': warnings
    }


if __name__ == "__main__":
    # Test structured reasoning creation
    print("=== Structured Reasoning Test ===\n")
    
    try:
        reasoning = create_reasoning_structure(
            observation="Memory pressure at 35% (signal #1234, 10:45 AM). Baseline p95: 27%. Deviation: +29.6%",
            hypothesis="Process 5678 has a memory leak causing gradual accumulation",
            evidence=[
                "Trend: +1.2% per minute over 30 minutes",
                "Confidence: 92% (r²=0.92)",
                "Process RSS: 800MB → 1.2GB in 2 hours"
            ],
            baseline_context="Current 35% vs baseline p95 27% → +29.6% deviation",
            predicted_outcome="OOM threshold (60%) in ~25 minutes. Risk: CRITICAL",
            recommended_action={
                "action_type": "lower_process_priority",
                "params": {"pid": 5678, "priority": 10},
                "command": "renice +10 -p 5678"
            },
            risks_and_rollback={
                "risks": ["Process slower"],
                "blast_radius": "single_process",
                "reversible": True,
                "rollback": "renice -10 -p 5678"
            },
            confidence=0.85,
            uncertainty_sources=["Limited historical data for this process"]
        )
        
        print("✓ Structured reasoning created successfully")
        print(f"  Confidence: {reasoning.confidence}")
        print(f"  Observation: {reasoning.observation[:50]}...")
        print(f"  Hypothesis: {reasoning.hypothesis}")
        
        # Validate
        validation = validate_reasoning_completeness(reasoning)
        print(f"\n✓ Validation: {validation['valid']}")
        if validation['warnings']:
            print(f"  Warnings: {validation['warnings']}")
        
    except ValueError as e:
        print(f"✗ Error: {e}")
    
    print("\n=== Test: Hallucinated Certainty Detection ===")
    try:
        bad_reasoning = create_reasoning_structure(
            observation="High memory (signal #1)",
            hypothesis="This will definitely cause OOM",  # BAD!
            evidence=["high usage"],
            baseline_context="above baseline",
            predicted_outcome="crash",
            recommended_action={"action_type": "test"},
            risks_and_rollback={"risks": []},
            confidence=0.5
        )
        print("✗ Should have rejected hallucinated certainty!")
    except ValueError as e:
        print(f"✓ Correctly rejected: {e}")

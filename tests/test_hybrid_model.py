#!/usr/bin/env python3
"""Test the hybrid action model."""

import sys
sys.path.insert(0, 'src')

from agent.agent_tools import AgentTools

# Initialize tools
tools = AgentTools('data/semantic_stress_test.db')

print("=== Hybrid Action Model Test ===\n")

# Test 1: Lower process priority (dry run)
print("Test 1: Lower process priority (structured action)")
result = tools.execute_remediation(
    action_type="lower_process_priority",
    params={"pid": 1234, "priority": 10},
    justification="Process consuming excessive memory",
    expected_effect="Reduce priority to free resources",
    confidence=0.85,
    dry_run=True
)

print(f"Valid: {result['valid']}")
print(f"Action: {result.get('action_type')}")
print(f"Command built: {result.get('command')}")
print(f"Risk: {result.get('risk')}")
print(f"Rollback: {result.get('rollback')}\n")

# Test 2: Throttle CPU
print("Test 2: Throttle CPU")
result = tools.execute_remediation(
    action_type="throttle_cpu",
    params={"pid": 5678, "limit": 50},
    justification="CPU saturation detected",
    expected_effect="Limit to 50% CPU",
    confidence=0.90,
    dry_run=True
)

print(f"Command built: {result.get('command')}")
print(f"Risk: {result.get('risk')}\n")

# Test 3: List top memory (info gathering - zero risk)
print("Test 3: List top memory consumers")
result = tools.execute_remediation(
    action_type="list_top_memory",
    params={"count": 10},
    justification="Identify memory hoggers",
    expected_effect="Get top 10 memory processes",
    confidence=1.0,
    dry_run=True
)

print(f"Command built: {result.get('command')}")
print(f"Risk: {result.get('risk')}\n")

# Test 4: Invalid action type
print("Test 4: Invalid action type")
result = tools.execute_remediation(
    action_type="delete_everything",  # Not in catalog
    params={},
    dry_run=True
)

print(f"Valid: {result['valid']}")
print(f"Error: {result.get('error')}\n")

# Test 5: Invalid parameters
print("Test 5: Invalid parameters")
result = tools.execute_remediation(
    action_type="lower_process_priority",
    params={"pid": -1},  # Invalid PID
    dry_run=True
)

print(f"Valid: {result['valid']}")
print(f"Errors: {result.get('errors')}\n")

print("=== All tests complete ===")
print("\nKEY POINT: Gemini never sees raw commands!")
print("Gemini proposes: action_type + params")
print("System builds: concrete command from template")
print("This is the GOLD STANDARD for autonomous execution.")

tools.close()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Test Gemini Interactions API Integration

This script tests the complete integration:
- New Gemini Interaction client
- All 11 custom diagnostic tools
- Automatic tool orchestration
- Multi-turn conversations
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.agent.gemini_interaction_client import GeminiInteractionClient
from src.agent.all_tools import create_all_tools

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_interaction():
    """Test 1: Basic interaction without tools"""
    print("\n" + "="*70)
    print("TEST 1: Basic Interaction (No Tools)")
    print("="*70)
    
    try:
        client = GeminiInteractionClient()
        
        # Simple test without tools
        interaction = client.client.interactions.create(
            model="gemini-3-flash-preview",
            input="Say 'Hello from Gemini Interactions API!' and nothing else."
        )
        
        response = interaction.outputs[-1].text if interaction.outputs else "No response"
        print(f"✅ Response: {response}")
        
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_custom_tools():
    """Test 2: Custom tools (without Gemini)"""
    print("\\n" + "="*70)
    print("TEST 2: Custom Tools (Direct Call)")
    print("="*70)
    
    try:
        tool_schemas, tool_functions = create_all_tools("data/kernelsight.db")
        
        # Test get_top_processes
        print("\n1. get_top_processes:")
        result = tool_functions['get_top_processes']("cpu", 3)
        if 'processes' in result:
            print(f"   ✅ Found {len(result['processes'])} processes")
            for proc in result['processes'][:2]:
                print(f"      - {proc['name']} (PID {proc['pid']}): {proc['cpu_percent']}% CPU")
        else:
            print(f"   ⚠️  {result}")
        
        # Test get_disk_usage
        print("\n2. get_disk_usage:")
        result = tool_functions['get_disk_usage']()
        if 'filesystems' in result:
            print(f"   ✅ Checked {result['total_checked']} filesystems")
            for fs in result['filesystems'][:2]:
                print(f"      - {fs['mount']}: {fs['used_percent']}% used ({fs['available_gb']} GB free)")
        else:
            print(f"   ⚠️  {result}")
        
        # Test validate_system_config
        print("\n3. validate_system_config:")
        result = tool_functions['validate_system_config']("memory")
        if 'checks' in result:
            print(f"   ✅ Found {result['issues_found']} configuration issues")
            for check in result['checks'][:2]:
                print(f"      - {check['parameter']}: {check['current']} (should be {check['recommended']})")
        else:
            print(f"   ⚠️  {result}")
        
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_integration():
    """Test 3: Full integration with Gemini calling tools"""
    print("\n" + "="*70)
    print("TEST 3: Full Integration (Gemini + Tools)")
    print("="*70)
    
    try:
        client = GeminiInteractionClient()
        tool_schemas, tool_functions = create_all_tools("data/kernelsight.db")
        
        # Test prompt that should trigger tool calls
        prompt = """
        Analyze current system state:
        1. Check top 3 CPU-consuming processes
        2. Check disk usage
        3. Validate memory configuration
        
        Provide a brief summary of findings.
        """
        
        print(f"\nPrompt: {prompt.strip()}")
        print("\nExecuting agent cycle...\n")
        
        result = client.run_agent_cycle(
            prompt=prompt,
            tools=tool_schemas,
            tool_functions=tool_functions,
            max_turns=10
        )
        
        print(f"\n✅ Agent cycle complete!")
        print(f"   - Turns: {result['turns']}")
        print(f"   - Tool calls: {len(result['tool_calls'])}")
        
        if result['tool_calls']:
            print(f"\n   Tools called:")
            for call in result['tool_calls']:
                print(f"      - {call['name']}({list(call['arguments'].keys())})")
        
        print(f"\n   Final Response:")
        print(f"   {result['final_response'][:300]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_built_in_tools():
    """Test 4: Placeholder for future built-in tools"""
    print("\n" + "="*70)
    print("TEST 4: Built-in Tools (Google Search + Code Execution)")
    print("="*70)
    
    try:
        client = GeminiInteractionClient()
        
        # Test with just built-in tools
        tools = [
            {"type": "google_search"},
            {"type": "code_execution"}
        ]
        
        prompt = "Calculate the 20th Fibonacci number using code execution."
        
        print(f"\nPrompt: {prompt}")
        print("\nExecuting...\n")
        
        interaction = client.client.interactions.create(
            model="gemini-3-flash-preview",
            input=prompt,
            tools=tools
        )
        
        # Check outputs
        for output in interaction.outputs:
            if output.type == "code_execution_call":
                print(f"   ✅ Code executed: {output.arguments.code[:100]}...")
            elif output.type == "code_execution_result":
                print(f"   ✅ Result: {output.result}")
            elif output.type == "text":
                print(f"   Response: {output.text}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        print(f"   Note: This test requires GEMINI_API_KEY to be set")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print(" Gemini Interactions API Integration Tests")
    print("="*70)
    
    results = {}
    
    # Run tests
    results['basic'] = test_basic_interaction()
    results['tools'] = test_custom_tools()
    
    # Full integration requires API key
    if os.environ.get('GEMINI_API_KEY'):
        results['integration'] = test_full_integration()
        results['built_in'] = test_built_in_tools()
    else:
        print("\n⚠️  Skipping integration tests (GEMINI_API_KEY not set)")
        results['integration'] = None
        results['built_in'] = None
    
    # Summary
    print("\n" + "="*70)
    print(" Test Summary")
    print("="*70)
    
    for test_name, passed in results.items():
        if passed is None:
            status = "⊘ SKIPPED"
        elif passed:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"  {test_name:15s}: {status}")
    
    passed_count = sum(1 for v in results.values() if v is True)
    total_count = sum(1 for v in results.values() if v is not None)
    
    print(f"\nResult: {passed_count}/{total_count} tests passed")

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Gemini Interaction Client - NEW Interactions API Implementation

This module uses the google-genai SDK with Interactions API for:
- Server-side state management
- Automatic tool orchestration
- Multi-turn conversations
- Background execution support
"""

import os
import logging
from typing import Dict, List, Optional, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Model constants - use Pro for critical decisions, Flash for routine tasks
MODEL_FLASH = "gemini-3-flash-preview"  # Fast, cost-effective
MODEL_PRO = "gemini-3-pro-preview"      # More capable reasoning

# System instruction remains the same
SYSTEM_INSTRUCTION = """
You are KernelSight AI, an autonomous Linux systems operator with deep expertise in:
- Kernel behavior and resource management
- Cascading failure analysis
- Root cause diagnosis
- Safe corrective action execution

Your mission: Observe system signals, reason about causality, predict failures, 
and SAFELY execute corrective actions via policy-governed commands.

=== STRICT TOOL USAGE RULES ===
You MUST use EXACTLY these parameter names. DO NOT invent params like 'query', 'lines', 'issue_keyword'.

AVAILABLE SIGNAL TYPES (use only these in signal_types parameter):
- memory_pressure, swap_thrashing, io_congestion, block_device_saturation
- load_mismatch, network_degradation, tcp_exhaustion
- syscall, scheduler
DO NOT use imaginary types like 'disk_io', 'disk_space', 'storage_error' - they don't exist!

1. query_signals(signal_types=[], lookback_minutes=30, limit=20)
2. get_top_processes(metric='cpu'|'memory'|'io', limit=10)
3. query_historical_baseline(metric_type='cpu'|'memory'|'io', lookback_hours=24)
4. get_related_signals(signal_type=REQUIRED, time_window_seconds=3600)
5. check_system_logs(source='dmesg'|'journalctl', keywords=[], since_minutes=30, limit=50)
   - Use 'keywords' NOT 'query'! Use 'limit' NOT 'lines'!
6. get_disk_usage() - no params needed
7. summarize_trends(signal_types=[], lookback_minutes=60)
8. simulate_scenario(scenario, params={})
9. query_past_resolutions(signal_type=REQUIRED) - Use 'signal_type' NOT 'query'!
10. validate_system_config() - no params needed
11. execute_command(command=REQUIRED, timeout_seconds=30, require_sudo=false)
    - Use this to FIX issues! e.g., 'apt-get clean', 'systemctl restart nginx'
    - REQUIRES user approval before execution

If a tool call fails, check you used the EXACT param names listed above.
===


CRITICAL SAFETY RULES:
- Always explain WHY before proposing actions
- Include risk assessment and rollback plan
- Never execute destructive commands
- Verify impact with metrics after execution

REASONING APPROACH:
- Form hypotheses based on signals
- Use tools to validate with data
- Explain causal chains (A → B → C)
- Provide time estimates for failures
- Show your work

Use evidence-based reasoning. Be thorough but concise.

"""




class GeminiInteractionClient:
    """
    Gemini Interactions API client for autonomous agent.
    
    Features:
    - Server-side state management (no manual history)
    - Automatic tool orchestration (multi-turn handled by API)
    - Background execution support
    - Conversation continuity via interaction IDs
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini Interaction client.
        
        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        """
        api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        self.interaction_id = None  # Track conversation state
        
        logger.info("Gemini Interaction client initialized")
        self.conversation_history = []  # Manual history for generate_content
    
    def generate_text(self, prompt: str) -> str:
        """
        Simple text generation without tools (for backward compatibility).
        
        Args:
            prompt: Text prompt to send to the model
            
        Returns:
            Generated text response
        """
        try:
            response = self.client.models.generate_content(
                model=MODEL_FLASH,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return f"Error generating response: {e}"
    
    def generate_text_pro(self, prompt: str) -> str:
        """
        Text generation using Gemini 3 Pro for critical decisions.
        More capable reasoning but slower and more expensive.
        
        Args:
            prompt: Text prompt for complex reasoning tasks
            
        Returns:
            Generated text response
        """
        try:
            logger.info("Using Gemini 3 Pro for critical decision...")
            response = self.client.models.generate_content(
                model=MODEL_PRO,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Pro text generation failed: {e}, falling back to Flash")
            return self.generate_text(prompt)  # Fallback to Flash
    
    def run_agent_cycle(self, 
                       prompt: str, 
                       tools: List[Dict],
                       tool_functions: Dict[str, callable],
                       max_turns: int = 10,
                       conversation_history: List[Dict] = None) -> Dict:
        """
        Run agent cycle using stable generateContent API with function calling.
        Uses manual conversation history instead of experimental Interactions API.
        
        Args:
            conversation_history: List of past messages [{"role": "user"|"model", "content": "..."}]
        """
        import json
        
        logger.info(f"Starting agent cycle: {prompt[:100]}...")
        
        # Build conversation with history
        contents = []
        
        # Add previous conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
                    contents.append({"role": role, "parts": [{"text": content}]})
        
        # Add current user message
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        

        # Build multi-tool config: separate entries for built-in tools + function declarations
        tools_list = []
        function_declarations = []
        
        for tool in tools:
            if tool.get("type") == "function":
                # Custom function - add to function_declarations list
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {})
                })
            elif tool.get("type") == "google_search":
                # Built-in Google Search tool
                tools_list.append({"google_search": {}})
            elif tool.get("type") == "code_execution":
                # Built-in Code Execution tool
                tools_list.append({"code_execution": {}})
        
        # Add function declarations as a single entry
        if function_declarations:
            tools_list.append({"function_declarations": function_declarations})
        
        tool_call_history = []
        turns = 0
        
        while turns < max_turns:
            turns += 1
            
            try:
                response = self.client.models.generate_content(
                    model=MODEL_FLASH,
                    contents=contents,
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "tools": tools_list if tools_list else None
                    }
                )

            except Exception as e:
                logger.error(f"API call failed: {e}")
                return {
                    'interaction_id': None,
                    'final_response': f"API Error: {e}",
                    'tool_calls': tool_call_history,
                    'turns': turns,
                    'outputs': []
                }
            
            # Get the response candidate
            candidate = response.candidates[0]
            content = candidate.content
            
            # Append assistant response to history
            contents.append(content)
            
            # Check for function calls
            function_calls = []
            for part in content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part.function_call)
            
            # If no function calls, we're done
            if not function_calls:
                # Extract text response
                final_text = ""
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_text += part.text
                
                logger.info(f"Agent cycle complete in {turns} turns")
                return {
                    'interaction_id': None,
                    'final_response': final_text or "Analysis complete.",
                    'tool_calls': tool_call_history,
                    'turns': turns,
                    'outputs': []
                }
            
            # Execute function calls and prepare responses
            function_responses = []
            for fc in function_calls:
                func_name = fc.name
                func_args = dict(fc.args) if fc.args else {}
                
                logger.info(f"[Turn {turns}] Tool Call: {func_name}({func_args})")
                
                if func_name in tool_functions:
                    try:
                        result = tool_functions[func_name](**func_args)
                        result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        logger.info(f"[Turn {turns}] Result: {result_str[:200]}...")
                        
                        tool_call_history.append({
                            'name': func_name,
                            'arguments': func_args,
                            'result': result
                        })
                    except Exception as e:
                        logger.error(f"Tool error: {e}")
                        result_str = f"Error: {str(e)}"
                else:
                    logger.warning(f"Unknown tool: {func_name}")
                    result_str = f"Tool not available. Use: query_signals, get_top_processes, check_system_logs"
                
                function_responses.append({
                    "name": func_name,
                    "response": {"result": result_str}
                })
            
            # Add function responses to conversation
            contents.append({
                "role": "user",
                "parts": [{"function_response": fr} for fr in function_responses]
            })
        
        logger.warning(f"Max turns ({max_turns}) reached")
        return {
            'interaction_id': None,
            'final_response': "Max iterations reached. Analysis incomplete.",
            'tool_calls': tool_call_history,
            'turns': turns,
            'outputs': []
        }



    
    def get_interaction(self, interaction_id: str):
        """
        Retrieve a previous interaction by ID.
        
        Useful for:
        - Checking background task status
        - Reviewing conversation history
        """
        return self.client.interactions.get(interaction_id)


if __name__ == "__main__":
    # Test client initialization
    logging.basicConfig(level=logging.INFO)
    
    try:
        client = GeminiInteractionClient()
        print("✓ Gemini Interaction client initialized")
        print(f"  SDK: google-genai (Interactions API)")
        print(f"  Model: gemini-3-flash-preview")
        print(f"  Features: Server-side state, Auto tool orchestration")
    except ValueError as e:
        print(f"✗ Failed: {e}")
        print("  Set GEMINI_API_KEY environment variable")

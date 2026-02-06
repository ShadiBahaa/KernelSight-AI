#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
All Agent Tools - Unified tool registry for Gemini agent

This module provides the complete set of 11 custom diagnostic tools.
"""

import logging
from typing import Dict, List, Any
from src.agent.enhanced_tools import EnhancedAgentTools, ENHANCED_TOOL_SCHEMAS
from src.agent.agent_tools import AgentTools

logger = logging.getLogger(__name__)


def create_all_tools(db_path: str) -> tuple[List[Dict], Dict[str, callable]]:
    """
    Create complete tool set: schemas + function mappings.
    
    Args:
        db_path: Path to database
    
    Returns:
        (tool_schemas, tool_functions)
        - tool_schemas: List of JSON schemas for Gemini
        - tool_functions: Dict mapping tool names to Python functions
    """
    # Initialize tool classes
    enhanced_tools = EnhancedAgentTools(db_path)
    agent_tools = AgentTools(db_path)
    
    # ========================================================================
    # Custom Tool Schemas (7 tools)
    # ========================================================================
    tool_schemas = ENHANCED_TOOL_SCHEMAS.copy()
    
    # Add original agent tools
    tool_schemas.extend([
        {
            "type": "function",
            "name": "query_signals",
            "description": "Query recent semantic signals to understand current system state",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by signal types (empty = all)"
                    },
                    "severity_min": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Minimum severity"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum signals to return"
                    },
                    "lookback_minutes": {
                        "type": "integer",
                        "description": "How far back to look"
                    }
                },
                "required": []
            }
        },
        {
            "type": "function",
            "name": "summarize_trends",
            "description": "Analyze trends in system metrics to detect increasing/decreasing pressure",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Signal types to analyze"
                    },
                    "lookback_minutes": {
                        "type": "integer",
                        "description": "Window for trend calculation" 
                    }
                },
                "required": ["signal_types"]
            }
        },
        {
            "type": "function",
            "name": "simulate_scenario",
            "description": "Project future system state based on current trends",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_type": {
                        "type": "string",
                        "description": "Signal to project"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "How far to project into future"
                    }
                },
                "required": ["signal_type"]
            }
        }
    ])
    
    # ========================================================================
    # Function Mappings
    # ========================================================================
    tool_functions = {
        # Enhanced tools (8)
        "get_top_processes": enhanced_tools.get_top_processes,
        "query_historical_baseline": enhanced_tools.query_historical_baseline,
        "get_related_signals": enhanced_tools.get_related_signals,
        "check_system_logs": enhanced_tools.check_system_logs,
        "query_past_resolutions": enhanced_tools.query_past_resolutions,
        "get_disk_usage": enhanced_tools.get_disk_usage,
        "validate_system_config": enhanced_tools.validate_system_config,
        "execute_command": enhanced_tools.execute_command,

        # Original agent tools (3)
        "query_signals": agent_tools.query_signals,
        "summarize_trends": agent_tools.summarize_trends,
        "simulate_scenario": agent_tools.simulate_scenario,
    }
    
    logger.info(f"Created {len(tool_schemas)} tool schemas, {len(tool_functions)} functions")
    
    return tool_schemas, tool_functions


if __name__ == "__main__":
    # Test tool registry
    logging.basicConfig(level=logging.INFO)
    
    schemas, functions = create_all_tools("data/kernelsight.db")
    
    print("Tool Registry Summary:\n")
    print(f"Total Tools: {len(schemas)}")
    print(f"Functions: {len(functions)}")
    
    print("\nTool List:")
    for i, schema in enumerate(schemas, 1):
        if schema.get("type") == "function":
            print(f"  {i}. {schema['name']} (custom)")
        else:
            print(f"  {i}. {schema['type']} (built-in)")
    
    print("\nTest: Call get_top_processes")
    result = functions['get_top_processes']("cpu", 3)
    print(f"Result: Found {len(result.get('processes', []))} processes")

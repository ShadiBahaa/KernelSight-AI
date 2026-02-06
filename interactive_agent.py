#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Interactive Agent - Conversational interface with user oversight

This provides a user-friendly interface where:
1. Users can chat with the agent
2. See real-time reasoning and tool calls
3. Approve/reject actions before execution
4. Ask follow-up questions
"""

import sys
import os
import logging
from typing import Optional, List, Dict
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from datetime import datetime

# Enable readline for command history (up/down arrows work in WSL)
try:
    import readline
except ImportError:
    pass  # readline not available on Windows


# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.agent.gemini_interaction_client import GeminiInteractionClient
from src.agent.all_tools import create_all_tools

console = Console()
logger = logging.getLogger(__name__)


class InteractiveAgent:
    """
    Interactive agent with conversational UI and user oversight.
    
    Features:
    - Chat with agent about system state
    - See real-time reasoning
    - Approve actions before execution
    - Transparency into decision-making
    """
    
    def __init__(self, db_path: str = "data/kernelsight.db"):
        """Initialize interactive agent"""
        self.client = GeminiInteractionClient()
        self.tool_schemas, self.tool_functions = create_all_tools(db_path)
        self.conversation_history = []
        
        # User preferences
        self.require_approval = True  # Require approval for actions
        self.show_reasoning = True    # Show agent's thought process
        
        console.print(Panel(
            "[bold green]KernelSight AI - Interactive Agent[/bold green]\n"
            "Chat with your autonomous system operator\n"
            "Commands: /auto (toggle approval), /status, /history, /quit",
            title="🤖 Welcome",
            border_style="green"
        ))
    
    def chat(self):
        """
        Main conversational loop.
        
        User can:
        - Ask questions about system
        - Request analysis
        - Approve/reject proposed actions
        - See agent reasoning in real-time
        """
        while True:
            try:
                # Get user input (readline provides up/down arrow history in WSL)
                print()  # blank line
                user_input = input("\033[1;36mYou>\033[0m ").strip() or "/status"
                
                
                # Handle commands
                if user_input.startswith('/'):
                    if not self._handle_command(user_input):
                        break  # /quit
                    continue
                
                # Send to agent
                console.print("\n[bold yellow]🧠 Agent thinking...[/bold yellow]")
                
                result = self._agent_turn(user_input)
                
                # Display result
                self._display_response(result)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.exception("Error in chat loop")
    
    def _agent_turn(self, user_message: str) -> Dict:
        """
        Execute one agent turn with user oversight.
        
        Returns:
            {
                'response': '...',
                'tool_calls': [...],
                'actions_proposed': [...],
                'user_approved': True/False
            }
        """
        # Add to conversation
        self.conversation_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Call agent with tools
        # Wrap each tool function for approval/logging
        wrapped_functions = {
            name: lambda n=name, **kw: self._tool_wrapper(n, **kw)
            for name in self.tool_functions.keys()
        }
        
        result = self.client.run_agent_cycle(
            prompt=user_message,
            tools=self.tool_schemas,
            tool_functions=wrapped_functions,  # Dict of wrapped functions
            max_turns=10,
            conversation_history=self.conversation_history  # Pass history for context
        )

        
        # Add to history
        self.conversation_history.append({
            'role': 'agent',
            'content': result['final_response'],
            'tool_calls': result['tool_calls'],
            'timestamp': datetime.now().isoformat()
        })
        
        return result
    
    def _tool_wrapper(self, tool_name: str, **kwargs):
        """
        Wrapper around tools that shows calls and requests approval for actions.
        """
        # Show tool call
        if self.show_reasoning:
            console.print(f"\n[dim]🔧 Calling: {tool_name}({kwargs})[/dim]")
        
        # Check if this is an action that needs approval
        action_tools = ['execute_safe_command', 'execute_remediation']
        
        if tool_name in action_tools and self.require_approval:
            # Get action metadata for consequences
            action_type = kwargs.get('action_type', 'unknown')
            try:
                from src.agent.action_schema import ActionType, ACTION_CATALOG
                action_enum = ActionType(action_type)
                action_spec = ACTION_CATALOG.get(action_enum, {})
            except (ValueError, KeyError, ImportError):
                action_spec = {}
            
            # Build consequences display
            risk = action_spec.get('risk', 'unknown').upper()
            side_effects = action_spec.get('side_effects', [])
            rollback = action_spec.get('rollback_template') or action_spec.get('rollback', 'Manual intervention')
            expected_effect = kwargs.get('expected_effect', action_spec.get('description', 'N/A'))
            
            # Show what the action will do with consequences
            consequences_text = (
                f"[bold yellow]⚠️  Action Requested[/bold yellow]\n\n"
                f"Tool: {tool_name}\n"
                f"Action Type: {action_type}\n"
                f"Parameters: {kwargs}\n\n"
                f"[bold]📊 CONSEQUENCES:[/bold]\n"
                f"  Expected Effect: {expected_effect}\n"
                f"  Risk Level: {risk}\n"
            )
            if side_effects:
                consequences_text += f"  Side Effects: {', '.join(side_effects)}\n"
            consequences_text += f"  Rollback: {rollback}\n"
            
            console.print(Panel(consequences_text, border_style="yellow"))
            
            # Ask for approval
            approved = Confirm.ask("Do you approve this action?", default=False)
            
            if not approved:
                console.print("[red]❌ Action rejected by user[/red]")
                return {"error": "User rejected action", "approved": False}
            
            console.print("[green]✅ Action approved[/green]")

        
        # Execute tool
        try:
            result = self.tool_functions[tool_name](**kwargs)
            
            # Show result summary
            if self.show_reasoning and isinstance(result, dict):
                summary = result.get('summary', str(result)[:100])
                console.print(f"[dim]   → Result: {summary}[/dim]")
            
            return result
        except Exception as e:
            console.print(f"[red]   → Error: {e}[/red]")
            return {"error": str(e)}
    
    def _display_response(self, result: Dict):
        """Display agent response with rich formatting"""
        
        # Tool calls summary
        if result['tool_calls']:
            table = Table(title="🔧 Tools Used", show_header=True)
            table.add_column("Tool", style="cyan")
            table.add_column("Status", style="green")
            
            for call in result['tool_calls']:
                status = "✓" if 'error' not in call.get('result', {}) else "✗"
                table.add_row(call['name'], status)
            
            console.print(table)
        
        # Agent response
        console.print(Panel(
            Markdown(result['final_response']),
            title="[bold green]🤖 Agent[/bold green]",
            border_style="green"
        ))
        
        # Metadata
        console.print(f"[dim]Turns: {result['turns']} | Tools: {len(result['tool_calls'])}[/dim]")
    
    def _handle_command(self, command: str) -> bool:
        """
        Handle special commands.
        
        Returns:
            False if should quit, True otherwise
        """
        cmd = command.lower().strip()
        
        if cmd == '/quit' or cmd == '/exit':
            console.print("[yellow]Goodbye! 👋[/yellow]")
            return False
        
        elif cmd == '/auto':
            self.require_approval = not self.require_approval
            status = "OFF" if self.require_approval else "ON"
            console.print(f"[yellow]Autonomous mode: {status}[/yellow]")
            if not self.require_approval:
                console.print("[red]⚠️  Agent will execute actions WITHOUT approval![/red]")
        
        elif cmd == '/reasoning':
            self.show_reasoning = not self.show_reasoning
            status = "ON" if self.show_reasoning else "OFF"
            console.print(f"[yellow]Show reasoning: {status}[/yellow]")
        
        elif cmd == '/status':
            self._show_status()
        
        elif cmd == '/history':
            self._show_history()
        
        elif cmd == '/help':
            self._show_help()
        
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            console.print("Type /help for available commands")
        
        return True
    
    def _show_status(self):
        """Show current system status"""
        console.print(Panel(
            f"[bold]Agent Status[/bold]\n\n"
            f"Approval Required: {'✓' if self.require_approval else '✗'}\n"
            f"Show Reasoning: {'✓' if self.show_reasoning else '✗'}\n"
            f"Conversation Length: {len(self.conversation_history)} messages\n"
            f"Tools Available: {len(self.tool_schemas)}",
            title="📊 Status",
            border_style="blue"
        ))
    
    def _show_history(self):
        """Show conversation history"""
        console.print("\n[bold]Conversation History:[/bold]\n")
        
        for msg in self.conversation_history[-10:]:  # Last 10
            role = msg['role']
            icon = "👤" if role == 'user' else "🤖"
            style = "cyan" if role == 'user' else "green"
            
            console.print(f"[{style}]{icon} {role.title()}:[/{style}]")
            console.print(f"   {msg['content'][:150]}...")
            if 'tool_calls' in msg and msg['tool_calls']:
                console.print(f"   [dim]Tools: {[c['name'] for c in msg['tool_calls']]}[/dim]")
            console.print()
    
    def _show_help(self):
        """Show help"""
        help_text = """
# Available Commands

- `/quit` - Exit the agent
- `/auto` - Toggle autonomous mode (auto-approve actions)
- `/reasoning` - Toggle reasoning visibility
- `/status` - Show agent status
- `/history` - Show conversation history
- `/help` - Show this help

# Usage Tips

**Ask questions:**
- "What's causing high memory usage?"
- "Are there any critical signals?"
- "Check if disk space is OK"

**Request analysis:**
- "Analyze current system state"
- "Find cascading failures"
- "Compare to baseline"

**Get recommendations:**
- "What actions would help with memory pressure?"
- "Should I be worried about this load?"

The agent will use all 11 tools to provide comprehensive answers!
"""
        console.print(Panel(Markdown(help_text), title="📖 Help", border_style="blue"))


def main():
    """Run interactive agent"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Interactive KernelSight AI Agent")
    parser.add_argument('--db', default='data/kernelsight.db', help='Database path')
    parser.add_argument('--auto', action='store_true', help='Start in autonomous mode')
    parser.add_argument('--no-reasoning', action='store_true', help='Hide reasoning')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,  # Hide debug logs in interactive mode
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create agent
    agent = InteractiveAgent(db_path=args.db)
    
    if args.auto:
        agent.require_approval = False
        console.print("[yellow]⚠️  Started in AUTONOMOUS mode - actions will auto-execute![/yellow]")
    
    if args.no_reasoning:
        agent.show_reasoning = False
    
    # Start chat
    try:
        agent.chat()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Goodbye! 👋[/yellow]")


if __name__ == "__main__":
    main()

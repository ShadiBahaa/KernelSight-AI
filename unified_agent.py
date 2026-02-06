#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Unified Agent - Combined Interactive + Autonomous Monitoring

This provides a single unified interface where:
1. Background thread monitors system every N seconds
2. Alerts appear inline in chat when issues detected
3. User can chat, ask questions, or respond to alerts
4. Single terminal instead of two separate ones
"""

import sys
import os
import logging
import threading
import time
import queue
from typing import Optional, List, Dict
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table

# Enable readline for command history
try:
    import readline
except ImportError:
    pass

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.agent.gemini_interaction_client import GeminiInteractionClient
from src.agent.all_tools import create_all_tools

console = Console()
logger = logging.getLogger(__name__)


class UnifiedAgent:
    """
    Unified agent combining interactive chat with autonomous background monitoring.
    
    Features:
    - Background monitoring thread (configurable interval)
    - Inline alerts when issues detected
    - Interactive chat for on-demand queries
    - Shared conversation history
    - Single terminal interface
    """
    
    def __init__(self, db_path: str = "data/kernelsight.db", 
                 monitor_interval: int = 60):
        """
        Initialize unified agent.
        
        Args:
            db_path: Path to SQLite database
            monitor_interval: Seconds between background checks (0 = disabled)
        """
        self.db_path = db_path
        self.monitor_interval = monitor_interval
        
        # Initialize Gemini client and tools
        self.client = GeminiInteractionClient()
        self.tool_schemas, self.tool_functions = create_all_tools(db_path)
        
        # Conversation state
        self.conversation_history = []
        self.require_approval = True
        self.show_reasoning = True
        
        # Background monitoring
        self.alert_queue = queue.Queue()
        self.monitor_thread = None
        self.running = False
        self.last_check_time = None
        self.issues_found = 0
        
        # Print welcome
        self._show_welcome()
    
    def _show_welcome(self):
        """Show welcome message"""
        monitor_status = f"ON (every {self.monitor_interval}s)" if self.monitor_interval > 0 else "OFF"
        console.print(Panel(
            f"[bold green]KernelSight AI - Unified Agent[/bold green]\n\n"
            f"🔄 Background Monitoring: {monitor_status}\n"
            f"💬 Chat: Ask questions anytime\n"
            f"✅ Approval: Required for actions\n\n"
            f"Commands: /auto, /monitor, /status, /quit",
            title="🤖 Welcome",
            border_style="green"
        ))
    
    def start(self):
        """Start the unified agent (background monitor + chat loop)"""
        self.running = True
        
        # Start background monitoring thread
        if self.monitor_interval > 0:
            self.monitor_thread = threading.Thread(
                target=self._background_monitor,
                daemon=True
            )
            self.monitor_thread.start()
            console.print(f"[dim]Background monitoring started ({self.monitor_interval}s interval)[/dim]\n")
        
        # Start interactive chat loop
        self._chat_loop()
    
    def _background_monitor(self):
        """Background thread that periodically checks system state"""
        while self.running:
            try:
                # Wait for interval
                time.sleep(self.monitor_interval)
                
                if not self.running:
                    break
                
                # Run quick health check
                self.last_check_time = datetime.now()
                alert = self._quick_health_check()
                
                if alert:
                    self.issues_found += 1
                    self.alert_queue.put(alert)
                    
            except Exception as e:
                logger.error(f"Background monitor error: {e}")
    
    def _quick_health_check(self) -> Optional[Dict]:
        """
        Quick health check - runs without Gemini to be fast.
        Returns alert dict if issues found, None otherwise.
        """
        try:
            # Check for critical signals
            signals_result = self.tool_functions['query_signals'](
                severity_min='high',
                lookback_minutes=5,
                limit=5
            )
            
            critical_signals = signals_result.get('signals', [])
            
            if critical_signals:
                # Found issues - create alert
                summaries = [s.get('summary', 'Unknown issue') for s in critical_signals[:3]]
                return {
                    'type': 'signal_alert',
                    'severity': 'high',
                    'count': len(critical_signals),
                    'summaries': summaries,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Quick process check
            procs = self.tool_functions['get_top_processes']('cpu', 3)
            top_cpu = procs.get('processes', [])
            
            for proc in top_cpu:
                if proc.get('cpu_percent', 0) > 90:
                    return {
                        'type': 'cpu_alert',
                        'severity': 'medium',
                        'process': proc.get('name'),
                        'cpu': proc.get('cpu_percent'),
                        'timestamp': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Health check error: {e}")
            return None
    
    def _chat_loop(self):
        """Main chat loop with inline alerts"""
        while self.running:
            try:
                # Check for pending alerts
                self._display_pending_alerts()
                
                # Get user input
                print()
                user_input = input("\033[1;36mYou>\033[0m ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    if not self._handle_command(user_input):
                        break
                    continue
                
                # Process user message with agent
                console.print("\n[bold yellow]🧠 Thinking...[/bold yellow]")
                result = self._agent_turn(user_input)
                self._display_response(result)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Ctrl+C - type /quit to exit[/yellow]")
            except EOFError:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.exception("Chat loop error")
        
        self._shutdown()
    
    def _display_pending_alerts(self):
        """Display any pending alerts from background monitor"""
        while not self.alert_queue.empty():
            try:
                alert = self.alert_queue.get_nowait()
                self._display_alert(alert)
            except queue.Empty:
                break
    
    def _display_alert(self, alert: Dict):
        """Display a background alert"""
        alert_type = alert.get('type', 'unknown')
        severity = alert.get('severity', 'medium')
        
        color = 'red' if severity == 'high' else 'yellow'
        icon = '🚨' if severity == 'high' else '⚠️'
        
        if alert_type == 'signal_alert':
            summaries = alert.get('summaries', [])
            text = f"{icon} [bold {color}]ALERT: {alert.get('count')} critical signals[/bold {color}]\n"
            for s in summaries:
                text += f"  • {s}\n"
            text += "\n[dim]Type a message to investigate or respond[/dim]"
            
        elif alert_type == 'cpu_alert':
            text = (
                f"{icon} [bold {color}]ALERT: High CPU Usage[/bold {color}]\n"
                f"  Process: {alert.get('process')}\n"
                f"  CPU: {alert.get('cpu')}%\n"
                f"\n[dim]Type a message to investigate or respond[/dim]"
            )
        else:
            text = f"{icon} [bold {color}]ALERT: {alert}[/bold {color}]"
        
        console.print(Panel(text, border_style=color))
    
    def _agent_turn(self, user_message: str) -> Dict:
        """Execute agent turn with tools"""
        self.conversation_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Wrap tools for approval
        wrapped = {
            name: lambda n=name, **kw: self._tool_wrapper(n, **kw)
            for name in self.tool_functions.keys()
        }
        
        result = self.client.run_agent_cycle(
            prompt=user_message,
            tools=self.tool_schemas,
            tool_functions=wrapped,
            max_turns=10,
            conversation_history=self.conversation_history
        )
        
        self.conversation_history.append({
            'role': 'agent',
            'content': result['final_response'],
            'timestamp': datetime.now().isoformat()
        })
        
        return result
    
    def _tool_wrapper(self, tool_name: str, **kwargs):
        """Wrapper for tool calls with logging and approval"""
        if self.show_reasoning:
            console.print(f"[dim]🔧 {tool_name}({kwargs})[/dim]")
        
        # Check for action tools requiring approval
        if tool_name == 'execute_command' and self.require_approval:
            console.print(Panel(
                f"[bold yellow]⚠️ Action Requested[/bold yellow]\n\n"
                f"Command: {kwargs.get('command', 'N/A')}\n"
                f"Timeout: {kwargs.get('timeout_seconds', 30)}s",
                border_style="yellow"
            ))
            
            if not Confirm.ask("Approve?", default=False):
                console.print("[red]❌ Rejected[/red]")
                return {"error": "User rejected", "approved": False}
            console.print("[green]✅ Approved[/green]")
        
        # Execute tool
        try:
            result = self.tool_functions[tool_name](**kwargs)
            if self.show_reasoning and isinstance(result, dict):
                summary = result.get('summary', str(result)[:80])
                console.print(f"[dim]   → {summary}[/dim]")
            return result
        except Exception as e:
            console.print(f"[red]   → Error: {e}[/red]")
            return {"error": str(e)}
    
    def _display_response(self, result: Dict):
        """Display agent response"""
        if result['tool_calls']:
            table = Table(title="🔧 Tools Used", show_header=True)
            table.add_column("Tool", style="cyan")
            table.add_column("Status")
            for call in result['tool_calls']:
                status = "✓" if 'error' not in call.get('result', {}) else "✗"
                table.add_row(call['name'], status)
            console.print(table)
        
        console.print(Panel(
            Markdown(result['final_response']),
            title="[bold green]🤖 Agent[/bold green]",
            border_style="green"
        ))
    
    def _handle_command(self, command: str) -> bool:
        """Handle slash commands. Returns False to quit."""
        cmd = command.lower().strip()
        
        if cmd in ['/quit', '/exit']:
            console.print("[yellow]Goodbye! 👋[/yellow]")
            return False
        
        elif cmd == '/auto':
            self.require_approval = not self.require_approval
            status = "OFF (auto-approve)" if not self.require_approval else "ON (require approval)"
            console.print(f"[yellow]Approval mode: {status}[/yellow]")
        
        elif cmd == '/monitor':
            if self.monitor_interval > 0:
                self.monitor_interval = 0
                console.print("[yellow]Background monitoring: DISABLED[/yellow]")
            else:
                self.monitor_interval = 60
                console.print("[yellow]Background monitoring: ENABLED (60s)[/yellow]")
        
        elif cmd == '/reasoning':
            self.show_reasoning = not self.show_reasoning
            console.print(f"[yellow]Show reasoning: {'ON' if self.show_reasoning else 'OFF'}[/yellow]")
        
        elif cmd == '/status':
            last_check = self.last_check_time.strftime('%H:%M:%S') if self.last_check_time else 'Never'
            console.print(Panel(
                f"[bold]Unified Agent Status[/bold]\n\n"
                f"Background Monitor: {'ON' if self.monitor_interval > 0 else 'OFF'}\n"
                f"Monitor Interval: {self.monitor_interval}s\n"
                f"Last Check: {last_check}\n"
                f"Issues Found: {self.issues_found}\n"
                f"Approval Required: {'✓' if self.require_approval else '✗'}\n"
                f"Show Reasoning: {'✓' if self.show_reasoning else '✗'}\n"
                f"Conversation: {len(self.conversation_history)} messages\n"
                f"Tools: {len(self.tool_schemas)}",
                title="📊 Status",
                border_style="blue"
            ))
        
        elif cmd == '/help':
            console.print(Panel(
                "**Commands**\n"
                "- `/quit` - Exit\n"
                "- `/auto` - Toggle auto-approval\n"
                "- `/monitor` - Toggle background monitoring\n"
                "- `/reasoning` - Toggle reasoning display\n"
                "- `/status` - Show status\n"
                "- `/help` - Show this help\n\n"
                "**Usage**\n"
                "Just type questions naturally:\n"
                "- \"What's causing high CPU?\"\n"
                "- \"Check disk space\"\n"
                "- \"Analyze memory trends\"\n\n"
                "Background alerts appear inline - respond to investigate!",
                title="📖 Help",
                border_style="blue"
            ))
        
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
        
        return True
    
    def _shutdown(self):
        """Clean shutdown"""
        self.running = False
        console.print("[dim]Shutting down...[/dim]")


def main():
    """Run unified agent"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KernelSight AI Unified Agent")
    parser.add_argument('--db', default='data/kernelsight.db', help='Database path')
    parser.add_argument('--interval', type=int, default=60, help='Monitor interval (0=disabled)')
    parser.add_argument('--auto', action='store_true', help='Auto-approve actions')
    parser.add_argument('--no-monitor', action='store_true', help='Disable background monitoring')
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    interval = 0 if args.no_monitor else args.interval
    agent = UnifiedAgent(db_path=args.db, monitor_interval=interval)
    
    if args.auto:
        agent.require_approval = False
        console.print("[yellow]⚠️ Auto-approve mode enabled[/yellow]")
    
    agent.start()


if __name__ == "__main__":
    main()

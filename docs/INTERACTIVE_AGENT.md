# Interactive Agent - Quick Start Guide

## What is this?

An **interactive conversational interface** for KernelSight AI where you can:

- 💬 **Chat with the agent** about your system
- 👁️ **See what it's thinking** in real-time  
- ✅ **Approve actions** before they execute
- 🤔 **Ask follow-up questions**
- 📊 **Request analysis** on-demand

## Quick Start

```bash
# Basic usage
python3 interactive_agent.py

# Auto-approve actions (autonomous mode)
python3 interactive_agent.py --auto

# Hide reasoning details
python3 interactive_agent.py --no-reasoning
```

## Example Conversation

```
You: What's causing high memory usage?

🧠 Agent thinking...
🔧 Calling: get_top_processes({'metric': 'memory', 'limit': 5})
   → Result: Found 5 processes
🔧 Calling: query_historical_baseline({'metric_type': 'memory'})
   → Result: Current 85% vs baseline 30% (+8.6σ abnormal)
🔧 Calling: get_related_signals({'signal_type': 'memory_pressure'})
   → Result: Found cascading failures

🤖 Agent:
High memory usage (85%) is caused by Chrome (PID 1234) consuming 4.2GB.
This is abnormal - your baseline is 30%. I detected a cascade:
memory_pressure → oom_kill → load_spike

Recommendation: Kill Chrome process or restart it.

Would you like me to do this?

You: Yes, kill it

⚠️  Action Requested
Tool: execute_safe_command
Command: kill -9 1234

Do you approve this action? (y/n): y

✅ Action approved
✅ Chrome process terminated
Memory usage: 85% → 42% (normal)
```

## Commands

| Command | Description |
|---------|-------------|
| `/quit` | Exit the agent |
| `/auto` | Toggle autonomous mode |
| `/reasoning` | Toggle reasoning visibility |
| `/status` | Show agent status |
| `/history` | Show conversation |
| `/help` | Show help |

## Features

See exactly what the agent is doing:
```
🔧 Calling: query_historical_baseline({'metric_type': 'memory'})
🔧 Calling: get_top_processes({'metric': 'cpu', 'limit': 5})
```

### 2. Action Approval
Before executing system commands:
```
⚠️  Action Requested
Tool: execute_safe_command
Command: sysctl -w vm.swappiness=10

Do you approve? (y/n):
```

### 3. Conversational
Ask natural questions:
- "What's wrong with my system?"
- "Check disk space"
- "Why is CPU high?"
- "Find related issues"

### 4. Educational
Learn from the agent:
- Explains reasoning
- Shows correlation analysis
- References documentation
- Provides rationale for actions

## Use Cases

### Troubleshooting
```
You: Why is my system slow?
Agent: [analyzes signals, processes, logs]
       Root cause: Disk at 98%, causing swap thrashing
```

### Monitoring
```
You: /status
Agent: System healthy
       - 3 minor warnings (disk 85%)
       - No critical issues
       - 5 signals in last hour
```

```
You: What does vm.swappiness do?
Agent: vm.swappiness controls how aggressively the kernel
       moves pages to swap. Lower = prefer keeping in RAM.
```

### Preventive
```
You: Any potential problems?
Agent: [validates config, checks trends]
       Found: net.core.somaxconn=128 (should be 1024)
       Risk: Connection drops under load
```

## Modes

### 🛡️ **Supervised Mode** (Default)
- Require approval for actions
- See all reasoning
- Maximum control

### 🚀 **Autonomous Mode** (`--auto`)
- Auto-approve actions
- Faster execution
- Trust the agent

### 🔇 **Quiet Mode** (`--no-reasoning`)
- Hide tool calls
- Just see results
- Cleaner output

## Integration with Existing Tools

The interactive agent uses ALL your tools:

**11 Custom Tools:**
- get_top_processes
- query_historical_baseline
- get_related_signals
- check_system_logs
- query_past_resolutions
- get_disk_usage
- validate_system_config
- execute_command
- query_signals
- summarize_trends
- simulate_scenario

## Tips

1. **Start with questions** - Let the agent explore
2. **Use /reasoning** - Learn how it thinks
3. **Review actions** - Understand impact before approving
4. **Ask "why"** - Get explanations for decisions
5. **Check /history** - See conversation flow

## Example Scenarios

### Scenario 1: High Load Investigation
```
You: Load average is 15, investigate
Agent: [checks processes, baseline, logs, related signals]
       Found cascading failure...
       Recommendation: [data-driven action]
```

### Scenario 2: Configuration Check
```
You: Validate my system configuration
Agent: [runs validate_system_config for all categories]
       Found 3 issues: [list with rationale]
       Suggested fixes: [sysctl commands]
       Approve all? (y/n):
```

### Scenario 3: Trend Analysis
```
You: What's the memory trend over the last hour?
Agent: [summarize_trends]
       Memory pressure increasing steadily... [summary with projections]
```

## Keyboard Shortcuts

- `Ctrl+C` - Interrupt (doesn't quit)
- `Ctrl+D` - Quick quit
- `↑/↓` - Command history (terminal default)

## Logging

Logs are quiet by default in interactive mode. To see debug logs:

```bash
export LOG_LEVEL=DEBUG
python3 interactive_agent.py
```

## Next Steps

1. Try it: `python3 interactive_agent.py`
2. Ask a question
3. Watch the reasoning
4. Approve an action
5. See the results!

**You now have a conversational SRE assistant! 🎉**

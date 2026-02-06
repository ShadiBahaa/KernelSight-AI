# Agent Layer

**Autonomous reasoning engine** powered by Gemini 3 for intelligent system analysis.

## What the Agent Does

The agent is **NOT** a passive log summarizer. It actively:

✅ **Plans diagnostic actions** - Designs multi-step investigation workflows  
✅ **Decides which traces to collect** - Determines what data is needed for analysis  
✅ **Correlates signals over time** - Identifies causal relationships between metrics  
✅ **Issues structured tool calls** - Executes queries, diagnostics, and remediation actions  
✅ **Communicates in plain language** - Explains technical findings accessibly  
✅ **Suggests risk-aware fixes** - Recommends solutions with potential risks highlighted  
✅ **Executes actions safely** - Uses tools to apply fixes with dry-run validation  
✅ **Reasons about root causes** - Performs true causal inference, not just pattern matching

## Components

- `core/`: ReAct loop implementation
- `tools/`: Tool implementations for metric querying
- `prompts/`: Prompt templates and system prompts

## Deployment Options

### Local Deployment (Default)
Agent runs as a Python process, making Gemini API calls.

### Google AI Studio Deployment
Agent components can be deployed to Google AI Studio for:
- Reduced local resource requirements
- Better scalability
- Managed infrastructure

## To Be Implemented

- [ ] Tool interface for metric queries
- [ ] ReAct planning loop
- [ ] Prompt templates
- [ ] Response parsing and formatting
- [ ] Caching layer

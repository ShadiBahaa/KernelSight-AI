# ADR-002: Google Gemini 3 for Autonomous Agent Layer

## Context

KernelSight AI requires an **autonomous reasoning engine** that doesn't just summarize logs, but actively:

1. **Plans diagnostic actions** based on system state
2. **Decides which traces to collect** for investigation
3. **Correlates signals over time** to find root causes
4. **Issues structured tool calls** for multi-step analysis
5. **Reasons about causality** between metrics and events

We need an AI model capable of agentic behavior, tool orchestration, and technical domain reasoning.

## Decision

We will use **Google Gemini 3 Pro** as the foundation for the autonomous agent layer, with deployment flexibility between local API calls and Google AI Studio.

## Rationale

### Advantages of Gemini 3

1. **Autonomous Planning**: Multi-step reasoning for complex diagnostic workflows
2. **Active Decision-Making**: Determines which metrics to query and traces to collect based on context
3. **Temporal Correlation**: Analyzes signals over time to identify causality patterns
4. **Native Tool Calling**: First-class function calling for structured system interactions
5. **Large Context Window**: 1M+ tokens for analyzing extensive telemetry history
6. **Technical Competence**: Strong performance on system administration, debugging, and root cause analysis
7. **Deployment Flexibility**: 
   - Local API calls for on-premises deployments
   - Google AI Studio for cloud-based agent hosting
8. **Agentic Capabilities**: True ReAct-style planning and execution loops

### Alternatives Considered

1. **GPT-4**: Strong reasoning but limited deployment flexibility, higher cost
2. **Claude**: Good reasoning but less flexible deployment options
3. **Open-source LLMs**: Lower capability, requires significant infrastructure

### Deployment Options

**Option 1: Local API Calls (Default)**
- Python application makes Gemini API calls
- Agent logic runs on monitoring server
- Lower latency for tight integration

**Option 2: Google AI Studio**
- Agent components deployed to AI Studio
- Leverage managed infrastructure
- Better scalability for multi-tenant scenarios
- Reduced local resource requirements

## Consequences

### Positive

- State-of-the-art reasoning capabilities
- Flexible deployment to match organizational requirements
- Strong Google Cloud ecosystem integration
- Continuous model improvements

### Negative

- Requires API key management
- Internet connectivity needed (unless using local alternatives)
- Cost scales with usage
- Vendor-specific API

### Mitigation

- Abstract agent interface for potential model swapping
- Implement caching for repeated queries
- Rate limiting and cost controls
- Support for local fallback models in future

## Implementation Notes

### Tool Interface Design

Agent tools will include:
- `query_signals(severity, lookback, types)`: Retrieve semantic signals
- `summarize_trends(signal_type, window)`: Detect patterns in history
- `simulate_scenario(signal_type, duration)`: Project future outcomes
- `propose_action(failure_mode, urgency)`: Get remediation options
- `execute_remediation(action_type, params)`: Execute safe actions

### Prompt Engineering

- Use structured system prompts with domain knowledge
- Provide metric specifications in context
- Include few-shot examples for common analyses

### Google AI Studio Considerations

For deployments using AI Studio:
- Agent logic can be deployed as Functions
- Reduces local compute requirements
- Enables easier updates and versioning
- Better suited for SaaS offerings

## References

- [Google Gemini API Documentation](https://ai.google.dev/)
- [Google AI Studio](https://aistudio.google.com/)
- [Function Calling Guide](https://ai.google.dev/docs/function_calling)

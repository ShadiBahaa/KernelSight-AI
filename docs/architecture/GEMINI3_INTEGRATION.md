# KernelSight AI - Gemini 3 Integration Notes

## Gemini 3 Role: Autonomous Reasoning Engine

Gemini 3 is the **core intelligence** of KernelSight AI, not just a passive summarization tool.

### What Gemini 3 Does

1. **Plans Diagnostic Actions**
   - Designs multi-step investigation workflows
   - Adapts plans based on intermediate findings
   - Prioritizes investigation paths

2. **Decides Which Traces to Collect**
   - Determines what additional data is needed
   - Requests specific metric time ranges
   - Triggers on-demand eBPF programs for focused collection

3. **Correlates Signals Over Time**
   - Analyzes temporal relationships between metrics
   - Identifies leading indicators of failures
   - Builds causal graphs from telemetry data

4. **Communicates in Human-Friendly Language**
   - Explains technical findings in plain, accessible terms
   - Translates kernel metrics into business impact
   - Provides context and background for non-experts

5. **Suggests Actionable Remediation**
   - Recommends specific actions to solve problems
   - Highlights potential risks and side effects of each action
   - Prioritizes fixes by impact and safety
   - Explains trade-offs between different solutions

6. **Executes Actions Using Tools**
   - `query_metrics(metric, time_range)` - Retrieve specific data
   - `get_anomalies(severity, window)` - Fetch detected anomalies
   - `explain_metric(name)` - Get metric documentation
   - `run_diagnostic(type)` - Execute system checks
   - `collect_trace(event, duration)` - Trigger focused data collection
   - `suggest_fix(problem, risk_tolerance)` - Generate remediation plan
   - `apply_fix(fix_id, dry_run)` - Execute remediation safely
   - `validate_fix(fix_id)` - Verify fix was successful

### Example Agent Workflow

**User Query**: "Why is the system slow?"

**Gemini 3 Reasoning & Actions**:
1. Query recent CPU metrics → sees high scheduler latency
2. Correlate with memory pressure → finds PSI spike
3. Decide to collect page fault traces
4. Issue tool call: `collect_trace('page_faults', 60)`
5. Analyze page fault patterns → identifies memory thrashing
6. Issue tool call: `query_metrics('mem.slab.utilization', last_1h)`
7. Find slab allocator exhaustion

**Human-Friendly Response**:
```
🔍 Root Cause Found:
Your system is slow because the kernel's memory allocator (slab) has run out 
of space, forcing it to constantly swap memory to disk. Think of it like a 
desk that's too small - you keep having to move papers to the filing cabinet, 
which takes time.

⚠️ Recommended Fixes (in order of safety):

1. SAFE: Restart memory-heavy services
   • Impact: Frees up slab memory immediately
   • Risk: Brief service interruption (2-5 seconds)
   • Command: systemctl restart [identified services]
   
2. MODERATE: Tune slab allocator parameters
   • Impact: Prevents future exhaustion
   • Risk: Requires testing; may need rollback
   • Command: sysctl vm.min_slab_ratio=5
   
3. HIGHER RISK: Upgrade kernel
   • Impact: Better memory management
   • Risk: Kernel upgrade requires reboot and testing
   • Recommendation: Schedule during maintenance window

Would you like me to execute option 1 (restart services)?
```

**If User Approves**:
8. Tool call: `apply_fix('restart_services', dry_run=True)` → preview changes
9. Tool call: `apply_fix('restart_services', dry_run=False)` → execute
10. Tool call: `validate_fix('restart_services')` → confirm slab normalized

### Tool Interface

```python
class AgentTools:
    # Investigation Tools
    def query_metrics(self, metric_name: str, start: str, end: str) -> List[Datapoint]:
        """Retrieve time-series data"""
        
    def get_anomalies(self, severity: str, time_range: str) -> List[Anomaly]:
        """Get detected anomalies"""
        
    def explain_metric(self, metric_name: str) -> str:
        """Get metric documentation and normal ranges"""
        
    def run_diagnostic(self, diagnostic_type: str) -> Dict:
        """Execute system diagnostic check"""
        
    def collect_trace(self, event_type: str, duration_sec: int) -> str:
        """Trigger on-demand eBPF trace collection"""
    
    # Remediation Tools
    def suggest_fix(self, problem: str, risk_tolerance: str = "low") -> List[Fix]:
        """Generate remediation options with risk assessment"""
        
    def apply_fix(self, fix_id: str, dry_run: bool = True) -> FixResult:
        """Execute a fix (dry_run=True previews changes)"""
        
    def validate_fix(self, fix_id: str) -> ValidationResult:
        """Verify fix resolved the issue"""
```

### Prompt Engineering

System prompts should emphasize:
- You are a helpful system performance expert
- Explain technical concepts in plain language
- You have access to kernel telemetry tools
- Plan before acting - think step by step
- Correlate metrics temporally to find root causes
- Always explain causality, not just correlation
- Suggest fixes with clear risk assessments
- Use analogies to make concepts accessible
- Prioritize user safety - dry-run before applying changes
- Confirm actions with users before execution

## Implementation Priority

Week 1-2: Basic tool interface  
Week 3-4: ReAct planning loop  
Week 5-6: Temporal correlation logic  
Week 7-8: On-demand trace collection

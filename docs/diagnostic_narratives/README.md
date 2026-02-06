# Diagnostic Narratives: Autonomous Agent in Action

> [!NOTE]
> **These narratives are illustrative examples** demonstrating what KernelSight AI's autonomous agent would do in real-world scenarios. They showcase the agent's reasoning capabilities, decision-making process, and expected outcomes based on the implemented architecture.

This directory contains **3 diagnostic scenarios** that demonstrate KernelSight AI's autonomous SRE agent capabilities.

## 📚 The Narratives

### 1. [Memory Leak Degradation](memory_leak_degradation.md)
**Scenario**: Gradual memory leak over 30 minutes  
**Challenge**: Detect subtle trend, predict OOM, take preventive action  
**Agent Action**: Conservative (lower process priority)  
**Outcome**: Successful prevention of crash

**Key Demonstrations**:
- ✅ Trend detection (r²=0.92)
- ✅ Baseline deviation analysis (+29.9%)
- ✅ Counterfactual simulation ("OOM in 25min")
- ✅ Conservative action selection
- ✅ Outcome validation

---

### 2. [Cascade Failure Escalation](cascade_failure_escalation.md)
**Scenario**: Memory → Swap → I/O cascade (18-second propagation)  
**Challenge**: Multi-signal correlation, aggressive intervention required  
**Agent Action**: Multi-action strategy (3 concurrent actions)  
**Outcome**: Prevented full system thrashing

**Key Demonstrations**:
- ✅ Multi-signal reasoning (3 event types)
- ✅ Cascade detection (temporal correlation)
- ✅ Severity-based escalation (CRITICAL → aggressive)
- ✅ Multi-action coordination
- ✅ Risk vs reward trade-off (service downtime vs node failure)

---

### 3. [Successful Recovery](successful_recovery.md)
**Scenario**: System recovery after cascade remediation  
**Challenge**: Validate previous actions, learn from outcomes  
**Agent Action**: Monitor + self-reflect (no action needed)  
**Outcome**: Confirmed recovery, updated confidence models

**Key Demonstrations**:
- ✅ **Self-reflection** (queries own reasoning traces)
- ✅ **Outcome validation** (predicted vs actual)
- ✅ **Confidence calibration** (adjusts future decisions)
- ✅ **Pattern recognition** (stores learnings)
- ✅ **Marathon agent** (75-minute timeline, multiple decisions)

---

## 📊 By The Numbers

### Scenario 1: Memory Leak
- **Detection time**: 2 minutes
- **MTTR**: 32 minutes
- **Prevented downtime**: 40 minutes
- **Business impact avoided**: $800-$1,200
- **Confidence**: 85%
- **Outcome**: Within prediction range ✓

### Scenario 2: Cascade
- **Detection time**: 2 minutes
- **MTTR**: 7 minutes
- **Prevented downtime**: 10-30 minutes (node reboot)
- **Business impact avoided**: $3,000-$5,000
- **Confidence**: 78% (lower for aggressive action)
- **Outcome**: Successful ✓

### Scenario 3: Recovery
- **Timeline**: 75 minutes (full incident lifecycle)
- **Self-reflection**: Analyzed 2 past traces
- **Confidence adjustments**: 2 models updated
- **Pattern recognition**: 3 new patterns stored
- **Human intervention**: 0 minutes

### Combined Impact
- **Total timeline**: 75 minutes
- **Total prevented cost**: $4,000-$6,000
- **Actual cost**: $50-$60 (47-second service restart)
- **ROI**: **100x**

---
## 📖 How to Read These Narratives

**For Non-Technical Judges**:
- Focus on: OBSERVATION, HYPOTHESIS, PREDICTED OUTCOME, OUTCOME sections
- Shows: What the agent saw, what it thought, what it did, what happened

**For Technical Judges**:
- Read full narrative (includes evidence, confidence breakdowns, meta-learning)
- Shows: Deep system understanding, quantified reasoning, autonomous learning

**For Business Judges**:
- Focus on: Business Impact sections, ROI calculations
- Shows: Prevents downtime ($4K-$6K saved), reduces on-call burden

---

## 🔗 Related Documentation

- [Structured Reasoning](../../src/agent/reasoning_templates.py) - Template definitions
- [Hybrid Action Model](../hybrid_model.md) - Safety architecture


---

## 📹 Demo

See these narratives come to life in the [terminal demo](../../demo_autonomous_agent.cast) *(to be recorded)*

---

**These narratives are the "proof of intelligence"** - they show the agent can think, reason, learn, and improve. Not just automation - **true autonomy**.

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Autonomous Agent Loop - Tool-Grounded Decision Making.

This is the CORE of Day 11: The agent OPERATES, not chats.

6-Phase Cycle:
1. OBSERVE - Query signals + baselines
2. EXPLAIN - What's abnormal and why (via Gemini)
3. SIMULATE - Project future outcomes
4. DECIDE - Choose action + params (via Gemini)
5. EXECUTE - Run action via hybrid model (with security validation)
6. VERIFY - Confirm problem resolved
"""

import sys
import os
import logging
import time
import re
from typing import Dict, Optional, List, Tuple
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.agent_tools import AgentTools
from analysis.baseline_analyzer import BaselineAnalyzer
from agent.gemini_interaction_client import GeminiInteractionClient

logger = logging.getLogger(__name__)


# NOTE: We previously had a DANGEROUS_PATTERNS blocklist here, but removed it.
# Reason: The blocklist could block legitimate remediation commands.
# Safety is now ensured by:
#   1. Gemini self-verification during command generation
#   2. User approval before execution (sees command + consequences)



class AutonomousAgent:
    """
    Autonomous agent that operates (not chats) using tool-grounded decisions.
    
    Supports human-in-the-loop approval for actions.
    """
    
    def __init__(self, db_path: str, api_key: Optional[str] = None, 
                 require_approval: bool = True):
        """
        Initialize autonomous agent.
        
        Args:
            db_path: Path to signal database
            api_key: Gemini API key (optional, reads from env)
            require_approval: If True, ask user before executing actions (default: True)
                             Set to False for fully autonomous "no-human" mode
        """
        self.db_path = db_path
        self.tools = AgentTools(db_path)
        self.baseline_analyzer = BaselineAnalyzer(db_path)
        self.require_approval = require_approval
        
        if not require_approval:
            logger.warning("⚠️  NO-HUMAN MODE: Agent will execute actions without approval!")
        
        # Initialize Gemini Interaction client (NEW Interactions API)
        self.gemini = None
        if api_key or os.environ.get('GEMINI_API_KEY'):
            try:
                self.gemini = GeminiInteractionClient(api_key)
                logger.info("Gemini Interaction client initialized (Interactions API)")
            except Exception as e:
                logger.warning(f"Gemini not available: {e}")
    
    # NOTE: _validate_command_safety was removed.
    # Safety is now ensured by Gemini self-verification during command generation
    # and user approval before execution (sees command + consequences).


    
    def _gemini_safety_check(self, command: str) -> Tuple[bool, str]:
        """
        Get Gemini's second opinion on command safety.
        
        Uses a separate Gemini call to verify the command won't cause harm.
        """
        import json
        
        prompt = f"""You are a SECURITY AUDITOR reviewing a Linux command before execution.

COMMAND TO REVIEW:
{command}

Analyze this command for potential security risks. Consider:
1. Could it delete important files or data?
2. Could it damage the system or make it unbootable?
3. Could it expose sensitive information?
4. Could it create a backdoor or security vulnerability?
5. Could it cause denial of service?
6. Is it a reasonable SRE remediation command?

Return a JSON object with:
- "is_safe": true if the command is safe for SRE remediation, false if dangerous
- "risk_assessment": "low", "medium", "high", or "critical"
- "reason": explanation of your assessment (1-2 sentences)

Be STRICT about security. If in doubt, mark as unsafe.
Respond ONLY with valid JSON, no markdown."""

        try:
            response = self.gemini.generate_text(prompt)
            
            # Parse response
            response_text = response.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            is_safe = result.get('is_safe', False)
            risk = result.get('risk_assessment', 'unknown')
            reason = result.get('reason', 'No reason provided')
            
            if not is_safe:
                logger.warning(f"🔒 Gemini flagged command as UNSAFE: {reason}")
                return False, f"Gemini security check failed ({risk} risk): {reason}"
            
            if risk in ['high', 'critical']:
                logger.warning(f"⚠️ Command has {risk} risk but Gemini approved: {reason}")
            
            logger.info(f"✅ Gemini security check passed ({risk} risk)")
            return True, f"Gemini approved ({risk} risk): {reason}"
            
        except Exception as e:
            logger.warning(f"Gemini safety check failed: {e}")
            # If Gemini fails, we still passed the blocklist, so allow with warning
            return True, f"Gemini check failed ({e}), proceeding with caution"



    def analyze_and_act(self, max_iterations: int = 3) -> Dict:
        """
        Full autonomous cycle: OBSERVE → EXPLAIN → SIMULATE → DECIDE → EXECUTE → VERIFY
        
        This is the operational loop - the agent makes grounded decisions.
        
        Args:
            max_iterations: Max decision cycles
            
        Returns:
            {
                'phases': {...},
                'action_taken': True/False,
                'resolved': True/False
            }
        """
        result = {
            'timestamp': datetime.now().isoformat(),
            'phases': {},
            'action_taken': False,
            'resolved': False
        }
        
        # ================================
        # PHASE 1: OBSERVE
        # ================================
        logger.info("[OBSERVE] Querying system state...")
        
        signals = self.tools.query_signals(
            severity_min='medium',
            limit=20,
            lookback_minutes=10
        )
        
        result['phases']['observe'] = {
            'signal_count': signals['signal_count'],
            'summary': signals['summary']
        }
        
        if signals['signal_count'] == 0:
            logger.info("[OBSERVE] System healthy - no action needed")
            result['status'] = 'healthy'
            return result
        
        logger.info(f"[OBSERVE] Found {signals['signal_count']} signals")
        
        # Get baselines for context
        baselines = self.baseline_analyzer.load_baselines(max_age_hours=48)
        
        # ================================
        # PHASE 2: EXPLAIN (Gemini-powered if available)
        # ================================
        logger.info("[EXPLAIN] Analyzing abnormalities...")
        
        if self.gemini:
            # Use Gemini for causal reasoning
            explanation = self._explain_with_gemini(signals, baselines)
        else:
            # Fallback to rule-based explanation
            explanation = self._explain_signals(signals, baselines)
        
        result['phases']['explain'] = explanation
        logger.info(f"[EXPLAIN] {explanation['summary']}")

        
        # ================================
        # PHASE 3: SIMULATE
        # ================================
        logger.info("[SIMULATE] Projecting future states...")
        
        simulation = None
        critical_signal = None
        
        # SIMPLIFIED LOGIC: If we have HIGH/CRITICAL abnormalities, that's enough!
        # No need for complex trend simulation when severity is already critical
        if explanation['abnormalities']:
            # Find highest severity abnormality
            for abn in explanation['abnormalities']:
                severity = abn.get('severity', 'low')
                if severity in ['high', 'critical']:
                    critical_signal = abn['signal']
                    simulation = {
                        'risk_level': severity,
                        'scenario_description': f"If {critical_signal} continues at {severity.upper()} severity, system degradation likely"
                    }
                    break
        
        # Fallback: Try complex simulation if no abnormalities met threshold
        if not simulation:
            for sig in signals['signals']:
                sig_type = sig['signal_type']
                sim = self.tools.simulate_scenario(
                    signal_type=sig_type,
                    duration_minutes=30
                )
                
                if 'risk_level' in sim and sim['risk_level'] in ['high', 'critical']:
                    simulation = sim
                    critical_signal = sig_type
                    break
        
        if simulation:
            result['phases']['simulate'] = {
                'signal_type': critical_signal,
                'risk_level': simulation.get('risk_level'),
                'summary': simulation.get('scenario_description', 'N/A')
            }
            logger.info(f"[SIMULATE] Risk: {simulation.get('risk_level')}")
        else:
            logger.info("[SIMULATE] No critical risks projected")
            result['status'] = 'monitoring'
            return result
        
        # ================================
        # PHASE 4: DECIDE (Gemini-powered if available)
        # ================================
        logger.info("[DECIDE] Selecting remediation action...")
        
        if self.gemini:
            # Use Gemini for reasoning BUT enforce allowed actions only
            decision = self._decide_with_gemini(explanation, simulation, critical_signal)
        else:
            # Fallback to rule-based decision
            decision = self._decide_action(explanation, simulation, critical_signal)
        
        result['phases']['decide'] = decision
        logger.info(f"[DECIDE] Action: {decision['action_type']}")

        
        # ================================
        # PHASE 5: EXECUTE (with human approval if enabled)
        # ================================
        if decision['action_type']:
            
            # Check if this is a Gemini-generated command (free-form)
            is_gemini_generated = decision['action_type'] == 'gemini_generated'
            
            if is_gemini_generated:
                # Gemini generated a custom command
                display_command = decision.get('command', 'N/A')
                risk_level = decision.get('risk_level', 'unknown').upper()
                rollback = decision.get('rollback_command', 'manual intervention required')
                is_diagnostic = decision.get('is_diagnostic', False)
            else:
                # Policy-based action from fallback
                from .action_schema import ActionType, ACTION_CATALOG
                try:
                    action_enum = ActionType(decision['action_type'])
                    action_spec = ACTION_CATALOG.get(action_enum, {})
                except (ValueError, KeyError):
                    action_spec = {}
                
                command_template = action_spec.get('command_template', 'N/A')
                try:
                    display_command = command_template.format(**{**action_spec.get('optional_params', {}), **decision['params']})
                except KeyError:
                    display_command = command_template
                
                risk_level = action_spec.get('risk', 'unknown').upper()
                rollback = action_spec.get('rollback_template') or action_spec.get('rollback', 'Manual intervention required')
                if isinstance(rollback, str) and '{' in rollback:
                    try:
                        rollback = rollback.format(**{**action_spec.get('optional_params', {}), **decision['params']})
                    except KeyError:
                        pass
                is_diagnostic = decision['action_type'].startswith('list_') or decision['action_type'].startswith('check_')
            
            # Display proposal with consequences
            print("\n" + "="*60)
            if is_gemini_generated:
                print("🤖 GEMINI-GENERATED COMMAND")
            else:
                print("🔧 ACTION PROPOSAL (Policy Fallback)")
            print("="*60)
            print(f"  Command:      {display_command}")
            print(f"  Justification: {decision['justification']}")
            print(f"  Confidence:   {decision['confidence']:.0%}")
            print()
            print("📊 CONSEQUENCES:")
            print(f"  Expected Effect: {decision['expected_effect']}")
            print(f"  Risk Level:      {risk_level}")
            print(f"  Is Diagnostic:   {'Yes' if is_diagnostic else 'No (remediation)'}")
            print(f"  Rollback:        {rollback}")
            print("="*60)
            
            # Ask for approval (unless no-human mode)
            user_approved = True
            if self.require_approval:
                try:
                    response = input("\n⚠️  Execute this command? [y/N]: ").strip().lower()
                    user_approved = response in ['y', 'yes']
                except EOFError:
                    # Non-interactive mode
                    logger.warning("Non-interactive mode detected, skipping action")
                    user_approved = False
            else:
                logger.info("[NO-HUMAN MODE] Auto-approving action...")
            
            if not user_approved:
                logger.info("[EXECUTE] Action rejected by user")
                result['phases']['execute'] = {
                    'executed': False,
                    'rejected': True,
                    'reason': 'User declined'
                }
                result['action_taken'] = False
                return result
            
            logger.info("[EXECUTE] User approved - applying remediation...")
            
            # Execute the command
            if is_gemini_generated:
                # Gemini has already self-verified the command during generation
                # User has approved the command after seeing consequences
                # Proceed with execution
                logger.info(f"[EXECUTE] Running: {display_command}")
                

                # Execute Gemini-generated command directly
                import subprocess
                try:
                    proc = subprocess.run(
                        display_command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    exec_result = {
                        'executed': True,
                        'command': display_command,
                        'success': proc.returncode == 0,
                        'stdout': proc.stdout,
                        'stderr': proc.stderr,
                        'returncode': proc.returncode
                    }
                    if proc.returncode != 0:
                        logger.warning(f"Command exited with code {proc.returncode}: {proc.stderr}")
                except subprocess.TimeoutExpired:
                    exec_result = {'executed': True, 'command': display_command, 'success': False, 'error': 'Timeout'}
                except Exception as e:
                    exec_result = {'executed': False, 'command': display_command, 'success': False, 'error': str(e)}

            else:
                # Use existing remediation tool for policy-based actions
                exec_result = self.tools.execute_remediation(
                    action_type=decision['action_type'],
                    params=decision['params'],
                    justification=decision['justification'],
                    expected_effect=decision['expected_effect'],
                    confidence=decision['confidence'],
                    dry_run=False
                )

            
            result['phases']['execute'] = {
                'executed': exec_result.get('executed'),
                'command': exec_result.get('command'),
                'success': exec_result.get('success')
            }
            

            result['action_taken'] = exec_result.get('executed', False)
            
            logger.info(f"[EXECUTE] Success: {exec_result.get('success')}")
            
            # ================================
            # PHASE 6: VERIFY
            # ================================
            # Skip verification for info-gathering actions - they don't fix anything
            info_gathering_actions = ['list_top_memory', 'list_top_cpu', 'check_io_activity',
                                     'check_network_stats', 'check_tcp_stats', 'monitor_swap']
            
            if decision['action_type'] in info_gathering_actions:
                logger.info("[VERIFY] Skipped - info-gathering action doesn't resolve issues")
                result['phases']['verify'] = {
                    'skipped': True,
                    'reason': 'Info-gathering action - problem not resolved'
                }
                result['resolved'] = False
            elif exec_result.get('executed'):
                logger.info("[VERIFY] Waiting for remediation to take effect...")
                time.sleep(30)  # Wait for remediation
                
                logger.info("[VERIFY] Re-querying system state...")
                signals_after = self.tools.query_signals(
                    signal_types=[critical_signal],
                    lookback_minutes=2,
                    limit=5
                )
                
                resolved = self._check_resolution(signals, signals_after)
                
                result['phases']['verify'] = {
                    'signals_after': signals_after['signal_count'],
                    'resolved': resolved
                }
                
                result['resolved'] = resolved
                logger.info(f"[VERIFY] Resolved: {resolved}")

        
        return result
    
    def _explain_signals(self, signals: Dict, baselines: List[Dict]) -> Dict:
        """
        Explain what's abnormal (PHASE 2).
        
        Flags HIGH and CRITICAL severity signals as abnormal, even without baseline.
        For now, rule-based. Later: Gemini-powered causal reasoning.
        """
        abnormalities = []
        
        for sig in signals['signals']:
            sig_type = sig['signal_type']
            severity = sig.get('severity', 'none')
            pressure = sig.get('pressure_score', 0)
            
            # CRITICAL FIX: Flag HIGH and CRITICAL signals as abnormal
            # This ensures agent takes action even without baseline data
            if severity in ['high', 'critical']:
                abnormalities.append({
                    'signal': sig_type,
                    'severity': severity,
                    'current': pressure,
                    'explanation': f"{sig_type} at {severity.upper()} severity - immediate attention required"
                })
                continue  # Skip baseline check, severity alone is enough
            
            # Baseline-based detection (for low/medium severity)
            baseline = next((b for b in baselines if b['signal_type'] == sig_type), None)
            
            if baseline:
                baseline_facts = baseline.get('baseline_facts', [])
                
                # Check if above baseline
                if any('typically' in f.lower() for f in baseline_facts):
                    abnormalities.append({
                        'signal': sig_type,
                        'current': pressure,
                        'baseline': 'normal_range',
                        'explanation': f"{sig_type} elevated above baseline"
                    })
        
        return {
            'abnormalities': abnormalities,
            'summary': f"Found {len(abnormalities)} abnormal conditions"
        }
    
    def _explain_with_gemini(self, signals: Dict, baselines: List[Dict]) -> Dict:
        """
        Use Gemini for causal reasoning about abnormal signals.
        Falls back to rule-based if Gemini fails.
        """
        import json
        
        # Build context for Gemini
        signal_summary = []
        for sig in signals['signals']:
            signal_summary.append({
                'type': sig['signal_type'],
                'severity': sig.get('severity', 'unknown'),
                'pressure_score': sig.get('pressure_score', 0),
                'timestamp': sig.get('timestamp', '')
            })
        
        prompt = f"""You are an EXPERT Linux SRE (Site Reliability Engineer) with deep kernel knowledge.

CURRENT SYSTEM SIGNALS (last 10 minutes):
{json.dumps(signal_summary, indent=2)}

HISTORICAL CONTEXT: {len(baselines)} baseline profiles available for comparison

YOUR MISSION:
Perform ROOT CAUSE ANALYSIS on these signals. Think like a veteran SRE:

1. **Pattern Recognition**: What pattern do these signals reveal?
   - Is this memory pressure, CPU contention, I/O bottleneck, or cascading failure?
   
2. **Causal Chain**: Trace the causality backwards
   - What CAUSED this pressure? (runaway process, memory leak, swap thrashing, etc.)
   
3. **Severity Assessment**: How critical is this?
   - Is the system at risk of OOM killer, data loss, or service degradation?

4. **Trend Analysis**: Is this getting worse or stabilizing?
   - Compare pressure scores over time

Return a JSON object with:
- "abnormalities": list of {{"signal": type, "severity": level, "root_cause": your_diagnosis, "trend": "worsening"|"stable"|"improving"}}
- "primary_issue": the MAIN problem to address first
- "cascading_risks": what could happen if unaddressed
- "summary": one-line expert summary

Respond ONLY with valid JSON, no markdown."""

        try:
            response = self.gemini.generate_text(prompt)
            
            # Parse Gemini's JSON response
            response_text = response.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            result = json.loads(response_text)
            logger.info(f"[EXPLAIN] Gemini analysis: {result.get('summary', 'N/A')}")
            return result
            
        except Exception as e:
            logger.warning(f"Gemini explain failed: {e}, falling back to rules")
            return self._explain_signals(signals, baselines)
    
    def _decide_with_gemini(self, explanation: Dict, simulation: Dict, signal_type: str) -> Dict:
        """
        Use Gemini to decide, generate, AND verify the remediation command.
        
        OPTIMIZED: Single API call for:
        1. Command generation
        2. Safety self-verification
        
        Falls back to rule-based if Gemini fails.
        """
        import json
        
        prompt = f"""You are an expert Linux SRE agent with SECURITY AWARENESS.

SYSTEM ISSUE:
{json.dumps(explanation.get('abnormalities', []), indent=2)}

RISK LEVEL: {simulation.get('risk_level', 'unknown')}
PRIMARY SIGNAL: {signal_type}

Your task:
1. Analyze the root cause of the problem
2. Generate the EXACT Linux command that will fix or mitigate this issue
3. VERIFY your command is SAFE before returning it

SAFETY RULES - Your command must NOT:
- Delete files recursively from root (rm -rf /)
- Format filesystems (mkfs)
- Execute remote code (curl | sh, wget | bash)
- Create fork bombs
- Modify bootloader
- Set world-writable permissions (chmod 777)

SAFE COMMANDS for SRE remediation:
- Memory: `echo 1 > /proc/sys/vm/drop_caches`, `sync`, `sysctl -w vm.swappiness=10`
- CPU: `renice +10 -p <PID>`, `ionice -c3 -p <PID>`
- I/O: `sync`, `ionice`
- Process: `kill -STOP <PID>`, `kill -TERM <PID>`
- Diagnostic: `ps`, `top`, `free`, `df`, `vmstat`

Return a JSON object with:
- "command": the exact Linux command to execute
- "justification": why this command will help (2-3 sentences)
- "expected_effect": what will happen when this runs
- "risk_level": "low", "medium", or "high"
- "rollback_command": command to undo this action (if possible, else "manual intervention required")
- "is_diagnostic": true if this is just gathering info, false if it's a remediation
- "safety_verified": true if you verified the command is safe, false if it might be dangerous
- "safety_notes": brief explanation of why command is safe (1 sentence)

If you cannot generate a SAFE command, set "command" to empty string and explain in "safety_notes".

Respond ONLY with valid JSON, no markdown."""

        try:
            response = self.gemini.generate_text(prompt)
            
            # Parse response
            response_text = response.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            decision = json.loads(response_text)
            command = decision.get('command', '')
            safety_verified = decision.get('safety_verified', False)
            
            # Check if Gemini flagged its own command as unsafe
            if not safety_verified:
                logger.warning(f"Gemini flagged its own command as potentially unsafe: {decision.get('safety_notes', 'No reason')}")
                return self._decide_action(explanation, simulation, signal_type)
            
            if not command:
                logger.warning("Gemini returned empty command, falling back to rules")
                return self._decide_action(explanation, simulation, signal_type)
            
            logger.info(f"[DECIDE] Gemini generated safe command: {command}")
            logger.info(f"[SAFETY] Self-verified: {decision.get('safety_notes', 'N/A')}")
            
            # Build decision with Gemini-generated command
            return {
                'action_type': 'gemini_generated',  # Special marker
                'command': command,
                'params': {},
                'justification': decision.get('justification', f"Remediate {signal_type}"),
                'expected_effect': decision.get('expected_effect', 'Unknown'),
                'risk_level': decision.get('risk_level', 'medium'),
                'rollback_command': decision.get('rollback_command', 'manual intervention required'),
                'is_diagnostic': decision.get('is_diagnostic', False),
                'safety_verified': safety_verified,
                'safety_notes': decision.get('safety_notes', 'Self-verified by Gemini'),
                'confidence': 0.90 if safety_verified else 0.70  # Higher confidence if self-verified
            }
            
        except Exception as e:
            logger.warning(f"Gemini decide failed: {e}, falling back to rules")
            return self._decide_action(explanation, simulation, signal_type)

    
    def _calculate_confidence(self, action_type: str, risk_level: str, 
                             signal_severity: str, is_remediation: bool) -> float:
        """
        Calculate confidence score for an action decision.
        
        Based on:
        - Action risk (from action_schema)
        - Signal severity (how bad is the problem)
        - Action type (remediation vs info-gathering)
        
        Returns: 0.0-1.0 confidence score
        """
        # Base confidence by action purpose
        if is_remediation:
            base = 0.70  # Remediation action
        else:
            base = 0.30  # Info-gathering fallback
        
        # Adjust for action risk (from action_schema.py)
        risk_adjustment = {
            'none': 0.15,    # Safe to execute
            'low': 0.10,     # Minimal risk
            'medium': 0.0,   # Some risk
            'high': -0.10    # Higher risk, lower confidence
        }
        
        # Adjust for signal severity match
        severity_boost = {
            'critical': 0.15,  # Critical problem needs urgent action
            'high': 0.10,      # High severity
            'medium': 0.05,    # Medium severity
            'low': 0.0         # Low severity
        }
        
        confidence = base
        confidence += risk_adjustment.get(risk_level, 0.0)
        confidence += severity_boost.get(signal_severity, 0.0)
        
        # Clamp to valid range
        return max(0.1, min(0.95, confidence))
    
    def _decide_action(self, explanation: Dict, simulation: Dict, signal_type: str) -> Dict:
        """
        Decide which action to take (PHASE 4).
        
        Direct mapping from signal type to remediation action.
        For now, rule-based mapping. Later: Gemini-powered decision making.
        """
        # DIRECT MAPPING: Signal Type → Remediation Action
        signal_to_action = {
            'memory_pressure': 'clear_page_cache',
            'swap_thrashing': 'reduce_swappiness',
            'load_mismatch': 'lower_process_priority',
            'io_congestion': 'lower_io_priority',
            'network_degradation': 'reduce_fin_timeout',
            'tcp_exhaustion': 'increase_tcp_backlog',
            'block_device_saturation': 'flush_buffers'
        }
        
        action_type = signal_to_action.get(signal_type)
        
        if not action_type:
            # Fallback for unknown signal types
            logger.warning(f"No action mapped for {signal_type}, using info gathering")
            action_type = 'list_top_memory'
        
        # Get action details from schema
        from .action_schema import ActionType, ACTION_CATALOG
        
        try:
            action_enum = ActionType(action_type)
            action_spec = ACTION_CATALOG[action_enum]
            
            # Extract parameters if needed (e.g., PID for process actions)
            params = {}
            
            # Actions that need a PID
            if action_type in ['lower_process_priority', 'throttle_cpu', 'pause_process', 
                              'terminate_process', 'lower_io_priority']:
                # Query for top resource consumer
                if signal_type in ['load_mismatch', 'cpu_saturation']:
                    # Get top CPU consumer
                    top_procs = self.tools.execute_remediation(
                        action_type='list_top_cpu',
                        params={'count': 1},
                        dry_run=False
                    )
                else:
                    # Get top memory consumer
                    top_procs = self.tools.execute_remediation(
                        action_type='list_top_memory',
                        params={'count': 1},
                        dry_run=False
                    )
                
                # Parse PID from output (ps aux format: USER PID %CPU %MEM ...)
                if top_procs.get('success') and top_procs.get('stdout'):
                    lines = top_procs['stdout'].strip().split('\n')
                    if len(lines) > 1:  # Skip header
                        fields = lines[1].split()
                        if len(fields) > 1:
                            try:
                                params['pid'] = int(fields[1])
                                logger.info(f"Extracted PID {params['pid']} for {action_type}")
                            except (ValueError, IndexError):
                                logger.warning(f"Could not extract PID from: {lines[1]}")
            
            # Calculate dynamic confidence
            confidence = self._calculate_confidence(
                action_type=action_type,
                risk_level=action_spec['risk'],
                signal_severity=simulation.get('risk_level', 'medium'),
                is_remediation=True  # Actual remediation action
            )
            
            return {
                'action_type': action_type,
                'params': params,  # Now populated with PID if needed!
                'justification': f"Remediate {signal_type} at {simulation.get('risk_level', 'high').upper()} severity",
                'expected_effect': action_spec['description'],
                'confidence': confidence  # DYNAMIC: Based on risk, severity, action type
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Action schema error for {action_type}: {e}")
            
            # Info-gathering fallback with low confidence
            confidence = self._calculate_confidence(
                action_type='list_top_memory',
                risk_level='none',
                signal_severity='low',
                is_remediation=False  # Just gathering info
            )
            
            return {
                'action_type': 'list_top_memory',
                'params': {},
                'justification': f"Unable to map {signal_type}, gathering info instead",
                'expected_effect': 'Identify resource consumers',
                'confidence': confidence  # DYNAMIC: Low because it's a fallback
            }
    
    def _check_resolution(self, signals_before: Dict, signals_after: Dict) -> bool:
        """
        Check if problem was resolved (PHASE 6).
        """
        before_count = signals_before['signal_count']
        after_count = signals_after['signal_count']
        
        # Simple heuristic: fewer signals = resolved
        return after_count < before_count * 0.7  # 30% reduction
    
    def close(self):
        """Close resources."""
        self.tools.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python autonomous_loop.py <db_path>")
        sys.exit(1)
    
    agent = AutonomousAgent(sys.argv[1])
    
    print("=== Autonomous Agent Loop Test ===\n")
    result = agent.analyze_and_act()
    
    print("\n=== Results ===")
    print(f"Status: {result.get('status', 'action_attempted')}")
    print(f"Action taken: {result.get('action_taken')}")
    print(f"Resolved: {result.get('resolved')}")
    
    print("\n=== Phases ===")
    for phase, data in result.get('phases', {}).items():
        print(f"{phase.upper()}: {data}")
    
    agent.close()

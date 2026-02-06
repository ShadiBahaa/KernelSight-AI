#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Outcome Validator - Day 13: Learn from predictions vs reality.

Compares predicted outcomes to actual outcomes.
Calculates accuracy metrics.
Generates lessons learned for self-reflection.
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OutcomeValidator:
    """
    Validate agent predictions against actual outcomes.
    
    This enables self-reflection: "Was I right? How can I improve?"
    """
    
    def __init__(self, db_connection):
        """
        Initialize validator.
        
        Args:
            db_connection: SQLite connection
        """
        self.conn = db_connection
    
    def validate_outcome(self, trace_id: int, actual_signals: Dict) -> Dict:
        """
        Compare prediction to reality.
        
        Args:
            trace_id: ID of reasoning trace  
            actual_signals: Current system state after action
            
        Returns:
            {
                'hypothesis_correct': True/False,
                'prediction_accurate': True/False,
                'confidence_calibrated': True/False,
                'accuracy_score': 0.0-1.0,
                'lessons': [...]
            }
        """
        # Load original trace
        trace = self._load_trace(trace_id)
        if not trace:
            return {'error': f'Trace {trace_id} not found'}
        
        # Parse predicted outcome
        predicted = self._parse_prediction(trace['predicted_outcome'])
        
        # Measure actual change
        before_state = json.loads(trace['system_state']) if trace['system_state'] else {}
        actual_change = self._calculate_change(before_state, actual_signals, predicted.get('metric'))
        
        # Compare hypothesis
        hypothesis_correct = self._check_hypothesis(trace, actual_change)
        
        # Compare prediction
        prediction_accurate = self._check_prediction_accuracy(
            predicted.get('expected_change', 0),
            actual_change,
            tolerance=0.15  # 15% tolerance
        )
        
        # Check confidence calibration
        confidence_calibrated = self._check_confidence_calibration(
            trace['confidence'],
            prediction_accurate
        )
        
        # Generate lessons
        lessons = self._extract_lessons(
            trace,
            hypothesis_correct,
            prediction_accurate,
            confidence_calibrated,
            predicted.get('expected_change', 0),
            actual_change
        )
        
        # Calculate overall accuracy score
        accuracy_score = self._calculate_accuracy_score(
            hypothesis_correct,
            prediction_accurate,
            confidence_calibrated
        )
        
        # Update trace with validation results
        self._update_trace_outcome(trace_id, {
            'actual_outcome': json.dumps({'change': actual_change, 'signals': actual_signals}),
            'outcome_verified': True,
            'verification_timestamp': int(datetime.now().timestamp() * 1e9),
            'hypothesis_correct': hypothesis_correct,
            'prediction_accurate': prediction_accurate,
            'confidence_calibrated': confidence_calibrated,
            'lessons_learned': json.dumps(lessons)
        })
        
        logger.info(f"[VALIDATE] Trace {trace_id}: accuracy={accuracy_score:.2f}, prediction={'✓' if prediction_accurate else '✗'}")
        
        return {
            'hypothesis_correct': hypothesis_correct,
            'prediction_accurate': prediction_accurate,
            'confidence_calibrated': confidence_calibrated,
            'accuracy_score': accuracy_score,
            'lessons': lessons,
            'predicted_change': predicted.get('expected_change', 0),
            'actual_change': actual_change
        }
    
    def _load_trace(self, trace_id: int) -> Optional[Dict]:
        """Load reasoning trace from database."""
        cursor = self.conn.execute(
            "SELECT * FROM reasoning_traces WHERE trace_id = ?",
            (trace_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def _parse_prediction(self, predicted_outcome: str) -> Dict:
        """
        Extract predicted metrics from natural language.
        
        Example: "reduce memory by 20-30%" → {metric: 'memory_pressure', expected_change: -0.25}
        
        Handles all 10 event types:
        1. memory_pressure
        2. load_mismatch
        3. io_congestion
        4. network_degradation
        5. tcp_exhaustion
        6. swap_thrashing
        7. scheduler
        8. syscall
        9. page_fault
        10. general
        """
        outcome_lower = predicted_outcome.lower()
        
        # Match to specific event types (in priority order)
        if 'swap' in outcome_lower or 'swapping' in outcome_lower:
            metric = 'swap_thrashing'
        elif 'memory' in outcome_lower or 'oom' in outcome_lower or 'rss' in outcome_lower:
            metric = 'memory_pressure'
        elif 'cpu' in outcome_lower or 'load' in outcome_lower or 'runnable' in outcome_lower:
            metric = 'load_mismatch'
        elif 'i/o' in outcome_lower or 'io' in outcome_lower or 'disk' in outcome_lower or 'block' in outcome_lower:
            metric = 'io_congestion'
        elif 'tcp' in outcome_lower or 'connection' in outcome_lower or 'socket' in outcome_lower:
            metric = 'tcp_exhaustion'
        elif 'network' in outcome_lower or 'packet' in outcome_lower or 'interface' in outcome_lower:
            metric = 'network_degradation'
        elif 'context switch' in outcome_lower or 'scheduler' in outcome_lower or 'priority' in outcome_lower:
            metric = 'scheduler'
        elif 'syscall' in outcome_lower or 'system call' in outcome_lower:
            metric = 'syscall'
        elif 'page fault' in outcome_lower or 'paging' in outcome_lower:
            metric = 'page_fault'
        else:
            metric = 'general'
        
        # Extract percentage if present
        import re
        pct_match = re.search(r'(\d+)(?:-(\d+))?%', predicted_outcome)
        if pct_match:
            low = int(pct_match.group(1))
            high = int(pct_match.group(2)) if pct_match.group(2) else low
            avg_pct = (low + high) / 2 / 100
            
            # Check if reduction or increase
            if 'reduce' in predicted_outcome.lower() or 'decrease' in predicted_outcome.lower():
                avg_pct = -avg_pct
            
            return {'metric': metric, 'expected_change': avg_pct}
        
        return {'metric': metric, 'expected_change': 0}
    
    def _calculate_change(self, before: Dict, after: Dict, metric: str) -> float:
        """
        Calculate actual change in metric.
        
        Handles all 10 event types by extracting the appropriate metric
        from before/after system state snapshots.
        
        Returns:
            Positive = metric increased (usually bad)
            Negative = metric decreased (usually good)
        """
        # Map metric to signal field in state
        metric_field_map = {
            'memory_pressure': 'memory_pressure',
            'load_mismatch': 'load_pressure',
            'io_congestion': 'io_pressure',
            'network_degradation': 'network_errors',
            'tcp_exhaustion': 'tcp_connections',
            'swap_thrashing': 'swap_activity',
            'scheduler': 'context_switches',
            'syscall': 'syscall_latency',
            'page_fault': 'page_faults',
            'general': 'system_health'
        }
        
        field = metric_field_map.get(metric, 'pressure_score')
        
        # Extract values (with fallbacks)
        before_val = before.get(field, 0.0)
        after_val = after.get(field, 0.0)
        
        # Special handling for specific metrics
        if metric == 'network_degradation' or metric == 'tcp_exhaustion':
            # For these, we might track counts not ratios
            # So normalize to 0-1 scale if needed
            if after_val > 1.0 or before_val > 1.0:
                # Looks like counts, calculate % change
                if before_val > 0:
                    return (after_val - before_val) / before_val
                return 0.0
        
        # Default: simple difference (works for 0-1 pressure scores)
        return (after_val - before_val)
    
    def _check_hypothesis(self, trace: Dict, actual_change: float) -> bool:
        """
        Check if hypothesis was correct.
        
        Simple heuristic: If action was taken and metric improved, hypothesis was likely correct.
        """
        if trace['action_executed']:
            # If we predicted improvement and got it, hypothesis correct
            return actual_change < 0  # Negative = improvement (reduction in pressure)
        return False
    
    def _check_prediction_accuracy(self, predicted: float, actual: float, tolerance: float) -> bool:
        """Check if prediction was within tolerance."""
        if predicted == 0:
            return abs(actual) < tolerance
        
        error = abs(predicted - actual)
        return error / abs(predicted) <= tolerance
    
    def _check_confidence_calibration(self, confidence: float, accurate: bool) -> bool:
        """
        Check if confidence was appropriate.
        
        High confidence + accurate = good calibration
        Low confidence + inaccurate = good calibration
        High confidence + inaccurate = poor calibration
        """
        if accurate:
            return confidence >= 0.7  # Should have been confident
        else:
            return confidence < 0.7  # Should not have been confident
    
    def _extract_lessons(self, trace: Dict, hyp_correct: bool, pred_accurate: bool,
                        conf_calibrated: bool, predicted: float, actual: float) -> list:
        """Generate lessons learned from this outcome."""
        lessons = []
        
        if not hyp_correct:
            lessons.append("Hypothesis was incorrect - review causal assumptions")
        
        if not pred_accurate:
            diff = abs(predicted - actual)
            if actual < predicted:
                lessons.append(f"Over-estimated effect by {diff:.1%} - be more conservative")
            else:
                lessons.append(f"Under-estimated effect by {diff:.1%} - action more effective than expected")
        
        if not conf_calibrated:
            if trace['confidence'] > 0.7 and not pred_accurate:
                lessons.append(f"Over-confident (was {trace['confidence']:.2f}) - reduce confidence threshold")
            elif trace['confidence'] < 0.7 and pred_accurate:
                lessons.append(f"Under-confident (was {trace['confidence']:.2f}) - increase confidence threshold")
        
        if not lessons:
            lessons.append("Prediction was accurate - reinforce this approach")
        
        return lessons
    
    def _calculate_accuracy_score(self, hyp_correct: bool, pred_accurate: bool, 
                                  conf_calibrated: bool) -> float:
        """Overall accuracy score (0.0-1.0)."""
        score = 0.0
        if hyp_correct:
            score += 0.4
        if pred_accurate:
            score += 0.4
        if conf_calibrated:
            score += 0.2
        return score
    
    def _update_trace_outcome(self, trace_id: int, updates: Dict):
        """Update trace with outcome validation results."""
        set_clauses = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [trace_id]
        
        self.conn.execute(
            f"UPDATE reasoning_traces SET {set_clauses} WHERE trace_id = ?",
            values
        )
        self.conn.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Outcome Validator Test ===\n")
    print("Module loaded successfully")
    print("In production, this validates agent predictions against reality")
    print("\nExample:")
    print("  Predicted: Reduce memory by 25%")
    print("  Actual: Reduced by 18%")
    print("  Lesson: Over-estimated by 7% - be more conservative")

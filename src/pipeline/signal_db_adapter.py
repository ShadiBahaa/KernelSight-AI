#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Signal Database Adapter

Bridges semantic classifiers and database storage.
Transforms semantic observations into signal_metadata entries.
"""

from typing import Dict
from src.pipeline.db_manager import DatabaseManager
from src.pipeline.signals import (
    SyscallObservation,
    SchedulerObservation,
    SystemObservation,
    PageFaultObservation
)


class SignalDatabaseAdapter:
    """Adapts semantic observations to database storage."""
    
    def __init__(self, db: DatabaseManager):
        """
        Initialize adapter.
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
    
    def store_syscall_observation(self, obs: SyscallObservation, source_id: int) -> int:
        """
        Store syscall observation as signal.
        
        Args:
            obs: SyscallObservation from classifier
            source_id: ID in syscall_events table
            
        Returns:
            Signal ID
        """
        signal = {
            'timestamp': obs.timestamp,
            'signal_category': 'symptom',  # High-latency syscalls are symptoms
            'signal_type': 'syscall',
            'scope': 'process',
            'semantic_label': obs.category.value,
            'severity': obs.severity.value,
            'pressure_score': min(1.0, obs.latency_ms / 500.0),  # Normalize to 0-1
            'summary': obs.summary,
            'patterns': obs.patterns,
            'reasoning_hints': obs.reasoning_hints,
            'source_table': 'syscall_events',
            'source_id': source_id,
            'entity_type': 'process',
            'entity_id': str(obs.context.get('pid', '')),
            'entity_name': obs.context.get('comm', ''),
            'context': obs.context
        }
        
        return self.db.insert_signal(signal)
    
    def store_scheduler_observation(self, obs: SchedulerObservation, source_id: int) -> int:
        """
        Store scheduler observation as signal.
        
        Args:
            obs: SchedulerObservation from classifier
            source_id: ID in sched_events table
            
        Returns:
            Signal ID
        """
        # Determine signal category based on state
        if obs.state.value == 'normal':
            category = 'baseline'
        elif obs.state.value in ['busy']:
            category = 'context'
        else:
            category = 'symptom'
        
        signal = {
            'timestamp': obs.timestamp,
            'signal_category': category,
            'signal_type': 'scheduler',
            'scope': 'process',
            'semantic_label': obs.state.value,
            'severity': obs.severity.value,
            'pressure_score': obs.metrics.get('context_switches_per_sec', 0) / 20000.0,
            'summary': obs.summary,
            'patterns': obs.patterns,
            'reasoning_hints': obs.reasoning_hints,
            'source_table': 'sched_events',
            'source_id': source_id,
            'entity_type': 'process',
            'entity_id': str(obs.pid),
            'entity_name': obs.comm,
            'context': obs.context
        }
        
        return self.db.insert_signal(signal)
    
    def store_system_observation(self, obs: SystemObservation, 
                                 source_table: str, source_id: int) -> int:
        """
        Store system metrics observation as signal.
        
        Args:
            obs: SystemObservation from classifier
            source_table: Source table name ('memory_metrics', 'tcp_stats', etc.)
            source_id: ID in source table
            
        Returns:
            Signal ID
        """
        # Determine signal category
        if obs.pressure_type.value == 'none':
            category = 'baseline'
        else:
            category = 'symptom'
        
        # Determine scope based on signal type
        scope_map = {
            'memory': 'system',
            'load': 'system',
            'io': 'device',
            'network': 'interface',
            'tcp': 'system'
        }
        scope = scope_map.get(obs.pressure_type.value.split('_')[0], 'system')
        
        signal = {
            'timestamp': obs.timestamp,
            'signal_category': category,
            'signal_type': obs.pressure_type.value,
            'scope': scope,
            'semantic_label': obs.pressure_type.value,
            'severity': obs.severity.value,
            'pressure_score': obs.pressure_score,
            'summary': obs.summary,
            'patterns': obs.patterns,
            'reasoning_hints': obs.reasoning_hints,
            'source_table': source_table,
            'source_id': source_id,
            'entity_type': None,  # System-wide
            'entity_id': None,
            'entity_name': None,
            'context': obs.context
        }
        
        return self.db.insert_signal(signal)


# Example usage
if __name__ == '__main__':
    # Create test observation
    from src.pipeline.signals import SyscallSemanticClassifier
    
    classifier = SyscallSemanticClassifier()
    event = {
        'timestamp': 1704470400000000000,
        'syscall_name': 'read',
        'latency_ms': 152.5,
        'comm': 'postgres',
        'pid': 1234,
        'tid': 1234,
        'cpu': 2,
        'uid': 1000,
        'ret_value': 4096,
        'is_error': False,
        'arg0': 5
    }
    
    obs = classifier.create_observation(event)
    
    # Store in database
    db = DatabaseManager('data/test_signals.db')
    db.init_schema()
    
    adapter = SignalDatabaseAdapter(db)
    signal_id = adapter.store_syscall_observation(obs, source_id=1)
    
    print(f"Stored signal ID: {signal_id}")
    
    # Query signals
    signals = db.query_signals(signal_type='syscall', severity='high', limit=10)
    print(f"\nFound {len(signals)} signals")
    
    for sig in signals:
        print(f"\n- {sig['summary']}")
        print(f"  Severity: {sig['severity']}")
        print(f"  Patterns: {sig['patterns']}")
    
    db.close()
    print("\nSignal adapter test successful!")

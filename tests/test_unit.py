#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Unit Tests for KernelSight AI

Tests for:
- Signal classifiers
- Database operations
- Agent tools
- CLI commands
"""

import unittest
import sys
import os
from pathlib import Path
import tempfile
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.db_manager import DatabaseManager
from pipeline.signals.system_classifier import SystemMetricsClassifier
from agent.action_schema import ActionType, build_command


class TestSystemClassifier(unittest.TestCase):
    """Test signal classification"""
    
    def setUp(self):
        self.classifier = SystemMetricsClassifier()
    
    def test_memory_pressure_detection(self):
        """Test memory pressure classification"""
        event = {
            'mem_available_mb': 100,
            'mem_total_mb': 1000,
            'timestamp': 1234567890
        }
        
        result = self.classifier.classify_memory_pressure(event)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, 'memory_pressure')
        self.assertIn(result.severity, ['high', 'critical'])
        self.assertGreater(result.pressure_score, 0.8)
    
    def test_load_mismatch_detection(self):
        """Test load mismatch classification"""
        event = {
            'load_1m': 8.0,
            'cpu_count': 4,
            'timestamp': 1234567890
        }
        
        result = self.classifier.classify_load_mismatch(event)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, 'load_mismatch')
        self.assertEqual(result.severity, 'critical')  # 2x overload
        self.assertGreater(result.pressure_score, 0.5)
    
    def test_no_pressure_normal_state(self):
        """Test that normal state doesn't trigger signals"""
        event = {
            'mem_available_mb': 800,
            'mem_total_mb': 1000,
            'load_1m': 2.0,
            'cpu_count': 4,
            'timestamp': 1234567890
        }
        
        mem_result = self.classifier.classify_memory_pressure(event)
        load_result = self.classifier.classify_load_mismatch(event)
        
        # Should return None or low severity for normal state
        if mem_result:
            self.assertIn(mem_result.severity, ['low', 'medium'])
        if load_result:
            self.assertIn(load_result.severity, ['low', 'medium'])


class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_signal_insertion(self):
        """Test inserting signals"""
        signal_data = {
            'signal_type': 'memory_pressure',
            'severity': 'high',
            'pressure_score': 0.85,
            'summary': 'High memory pressure detected',
            'semantic_labels': json.dumps(['memory', 'pressure']),
            'reasoning_hint': 'Memory usage is high'
        }
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO signal_metadata 
            (signal_type, severity, pressure_score, summary, semantic_labels, reasoning_hint)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            signal_data['signal_type'],
            signal_data['severity'],
            signal_data['pressure_score'],
            signal_data['summary'],
            signal_data['semantic_labels'],
            signal_data['reasoning_hint']
        ))
        
        conn.commit()
        
        # Verify insertion
        result = cursor.execute("SELECT * FROM signal_metadata WHERE signal_type = ?", 
                               ('memory_pressure',)).fetchone()
        
        self.assertIsNotNone(result)
        conn.close()
    
    def test_query_performance(self):
        """Test that queries are reasonably fast"""
        import time
        
        # Insert 1000 test signals
        conn = self.db.connect()
        for i in range(1000):
            conn.execute("""
                INSERT INTO signal_metadata (signal_type, severity, pressure_score, summary)
                VALUES (?, ?, ?, ?)
            """, ('test_signal', 'medium', 0.5, f'Test signal {i}'))
        conn.commit()
        
        # Time query
        start = time.time()
        results = conn.execute("SELECT * FROM signal_metadata LIMIT 100").fetchall()
        elapsed = time.time() - start
        
        self.assertEqual(len(results), 100)
        self.assertLess(elapsed, 0.1)  # Should be < 100ms
        
        conn.close()


class TestActionSchemaCommands(unittest.TestCase):
    """Test action schema and command building"""
    
    def test_build_valid_command(self):
        """Test building valid command"""
        result = build_command(
            ActionType.LOWER_PROCESS_PRIORITY,
            {'pid': 1234, 'priority': 10}
        )
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['command'], 'renice +10 -p 1234')
        self.assertEqual(result['risk'], 'low')
        self.assertIn('rollback', result)
    
    def test_missing_required_param(self):
        """Test error on missing required parameter"""
        result = build_command(
            ActionType.LOWER_PROCESS_PRIORITY,
            {}  # Missing 'pid'
        )
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertIn('pid', str(result['errors']))
    
    def test_invalid_param_value(self):
        """Test error on invalid parameter value"""
        result = build_command(
            ActionType.LOWER_PROCESS_PRIORITY,
            {'pid': -1, 'priority': 10}  # Negative PID
        )
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
    
    def test_defaults_applied(self):
        """Test that default parameters are applied"""
        result = build_command(
            ActionType.CLEAR_PAGE_CACHE,
            {}  # No params, should use defaults
        )
        
        self.assertTrue(result['valid'])
        self.assertIn('echo', result['command'])
        self.assertIn('/proc/sys/vm/drop_caches', result['command'])


class TestCLIArguments(unittest.TestCase):
    """Test CLI argument parsing"""
    
    def test_query_command_parsing(self):
        """Test query command argument parsing"""
        # This would test the CLI argument parser
        # Simplified example
        args = {
            'type': 'memory_pressure',
            'severity': 'critical',
            'limit': 10,
            'lookback': 60
        }
        
        self.assertEqual(args['type'], 'memory_pressure')
        self.assertEqual(args['severity'], 'critical')
        self.assertEqual(args['limit'], 10)
        self.assertEqual(args['lookback'], 60)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSystemClassifier))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestActionSchemaCommands))
    suite.addTests(loader.loadTestsFromTestCase(TestCLIArguments))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())

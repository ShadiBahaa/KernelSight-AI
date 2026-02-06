#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Tests for the KernelSight AI data pipeline.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'pipeline'))

from db_manager import DatabaseManager
from event_parsers import (
    parse_json_line, normalize_event, identify_event_type, EventType
)


class TestEventParsers(unittest.TestCase):
    """Test event parsing and identification."""
    
    def test_identify_syscall_event(self):
        """Test syscall event identification."""
        event = {
            "timestamp": 1234567890000000000,
            "syscall": 1,
            "latency_ms": 15.5
        }
        self.assertEqual(identify_event_type(event), EventType.SYSCALL)
    
    def test_identify_memory_event(self):
        """Test memory event identification."""
        event = {
            "timestamp": 1234567890000000000,
            "mem_total_kb": 8192000,
            "mem_available_kb": 4096000
        }
        self.assertEqual(identify_event_type(event), EventType.MEMORY)
    
    def test_identify_io_latency_event(self):
        """Test I/O latency event identification."""
        event = {
            "timestamp": 1234567890000000000,
            "read_count": 100,
            "read_p50_us": 1.5
        }
        self.assertEqual(identify_event_type(event), EventType.IO_LATENCY)
    
    def test_parse_json_line(self):
        """Test JSON line parsing."""
        json_line = '{"timestamp": 1234567890000000000, "syscall": 1, "latency_ms": 15.5}'
        result = parse_json_line(json_line)
        
        self.assertIsNotNone(result)
        event_type, event = result
        self.assertEqual(event_type, EventType.SYSCALL)
        self.assertEqual(event['syscall'], 1)
    
    def test_parse_invalid_json(self):
        """Test invalid JSON handling."""
        result = parse_json_line('not valid json')
        self.assertIsNone(result)
    
    def test_normalize_syscall_event(self):
        """Test syscall event normalization."""
        event = {
            "timestamp": 1234567890000000000,
            "syscall": 1,
            "latency_ms": 15.5,
            "is_error": True
        }
        
        normalized = normalize_event(EventType.SYSCALL, event)
        self.assertEqual(normalized['latency_ns'], 15500000)
        self.assertTrue(normalized['is_error'])


class TestDatabaseManager(unittest.TestCase):
    """Test database operations."""
    
    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)
        self.db.init_schema()
    
    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        os.unlink(self.temp_db.name)
    
    def test_schema_initialization(self):
        """Test schema is created properly."""
        stats = self.db.get_table_stats()
        
        # All tables should exist with 0 rows
        self.assertIn('syscall_events', stats)
        self.assertIn('memory_metrics', stats)
        self.assertIn('io_latency_stats', stats)
        self.assertEqual(stats['syscall_events'], 0)
    
    def test_insert_syscall_event(self):
        """Test inserting a syscall event."""
        event = {
            'timestamp': 1234567890000000000,
            'pid': 1234,
            'tid': 1234,
            'cpu': 0,
            'uid': 0,
            'syscall': 1,
            'syscall_name': 'write',
            'latency_ns': 15500000,
            'ret_value': 512,
            'is_error': False,
            'arg0': 3,
            'comm': 'test'
        }
        
        self.db.insert_syscall_event(event)
        self.db.commit()
        
        stats = self.db.get_table_stats()
        self.assertEqual(stats['syscall_events'], 1)
    
    def test_insert_memory_metrics(self):
        """Test inserting memory metrics."""
        metrics = {
            'timestamp': 1234567890000000000,
            'mem_total_kb': 8192000,
            'mem_free_kb': 2048000,
            'mem_available_kb': 4096000,
            'buffers_kb': 512000,
            'cached_kb': 2048000,
            'swap_total_kb': 4096000,
            'swap_free_kb': 4096000,
            'active_kb': 2048000,
            'inactive_kb': 1024000,
            'dirty_kb': 10240,
            'writeback_kb': 0
        }
        
        self.db.insert_memory_metrics(metrics)
        self.db.commit()
        
        stats = self.db.get_table_stats()
        self.assertEqual(stats['memory_metrics'], 1)
    
    def test_query(self):
        """Test querying data."""
        # Insert test data
        event = {
            'timestamp': 1234567890000000000,
            'pid': 1234,
            'tid': 1234,
            'cpu': 0,
            'uid': 0,
            'syscall': 1,
            'syscall_name': 'write',
            'latency_ns': 15500000,
            'ret_value': 512,
            'is_error': False,
            'arg0': 3,
            'comm': 'test'
        }
        
        self.db.insert_syscall_event(event)
        self.db.commit()
        
        # Query it back
        rows = self.db.query("SELECT * FROM syscall_events WHERE pid = ?", (1234,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['pid'], 1234)
        self.assertEqual(rows[0]['syscall_name'], 'write')


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)
        self.db.init_schema()
    
    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        os.unlink(self.temp_db.name)
    
    def test_full_pipeline(self):
        """Test full pipeline: parse → normalize → insert."""
        # Simulate different event types
        test_events = [
            '{"timestamp": 1234567890000000000, "pid": 1234, "tid": 1234, "cpu": 0, "uid": 0, "syscall": 1, "syscall_name": "write", "latency_ms": 15.5, "ret_value": 512, "is_error": false, "arg0": 3, "comm": "test"}',
            '{"timestamp": 1234567890000000000, "mem_total_kb": 8192000, "mem_available_kb": 4096000, "mem_free_kb": 2048000}',
            '{"timestamp": 1234567890000000000, "load_1min": 1.5, "load_5min": 1.2, "load_15min": 1.0}',
        ]
        
        for json_line in test_events:
            result = parse_json_line(json_line)
            self.assertIsNotNone(result)
            
            event_type, event = result
            normalized = normalize_event(event_type, event)
            
            # Insert based on type
            if event_type == EventType.SYSCALL:
                self.db.insert_syscall_event(normalized)
            elif event_type == EventType.MEMORY:
                self.db.insert_memory_metrics(normalized)
            elif event_type == EventType.LOAD:
                self.db.insert_load_metrics(normalized)
        
        self.db.commit()
        
        # Verify all were inserted
        stats = self.db.get_table_stats()
        self.assertEqual(stats['syscall_events'], 1)
        self.assertEqual(stats['memory_metrics'], 1)
        self.assertEqual(stats['load_metrics'], 1)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())

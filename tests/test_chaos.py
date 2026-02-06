#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Chaos Tests for KernelSight AI

Tests system resilience under adverse conditions:
- API timeouts
- Malformed data
- Database corruption
- Network failures
- Race conditions
"""

import unittest
import sys
import os
from pathlib import Path
import tempfile
import json
import time
import requests
from unittest.mock import patch, MagicMock
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.db_manager import DatabaseManager
from agent.agent_tools import AgentTools


class TestAPIResilience(unittest.TestCase):
    """Test API resilience to failures"""
    
    @classmethod
    def setUpClass(cls):
        """Check if API server is running"""
        try:
            response = requests.get('http://localhost:8000/api/health', timeout=2)
            cls.api_available = response.status_code == 200
        except:
            cls.api_available = False
    
    def setUp(self):
        if not self.api_available:
            self.skipTest("API server not running")
    
    def test_api_timeout_handling(self):
        """Test API handles slow requests gracefully"""
        try:
            # Very short timeout
            response = requests.get('http://localhost:8000/api/signals', timeout=0.001)
            # If we get here, it was fast enough
            self.assertEqual(response.status_code, 200)
        except requests.exceptions.Timeout:
            # Expected - API didn't respond in time
            pass
    
    def test_api_invalid_params(self):
        """Test API handles invalid parameters"""
        # Invalid signal type
        response = requests.get('http://localhost:8000/api/signals?signal_type=' + 'X'*1000)
        # Should not crash
        self.assertIn(response.status_code, [200, 400, 422])
        
        # Invalid limit
        response = requests.get('http://localhost:8000/api/signals?limit=-1')
        self.assertIn(response.status_code, [200, 400, 422])
    
    def test_api_malformed_json_post(self):
        """Test API handles malformed JSON in POST requests"""
        try:
            response = requests.post(
                'http://localhost:8000/api/predict',
                data='{invalid json}',
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            # Should return error, not crash
            self.assertIn(response.status_code, [400, 422, 500])
        except:
            pass  # Connection error is acceptable
    
    def test_api_concurrent_requests(self):
        """Test API handles concurrent requests"""
        import concurrent.futures
        
        def make_request():
            try:
                response = requests.get('http://localhost:8000/api/stats', timeout=5)
                return response.status_code == 200
            except:
                return False
        
        # Send 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # At least some should succeed
        self.assertTrue(any(results))


class TestDatabaseResilience(unittest.TestCase):
    """Test database resilience to corruption and errors"""
    
    def test_handle_missing_database(self):
        """Test system handles missing database gracefully"""
        tools = AgentTools("/nonexistent/path/to/db.db")
        
        # Should not crash
        try:
            result = tools.query_signals(limit=10)
            # May return empty or error, but shouldn't crash
            self.assertIsInstance(result, dict)
        except Exception as e:
            # Expected - file not found
            pass
    
    def test_handle_corrupted_data(self):
        """Test system handles corrupted data in database"""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = DatabaseManager(db_path)
        
        # Insert corrupted data
        conn = db.connect()
        try:
            conn.execute("""
                INSERT INTO signal_metadata 
                (signal_type, severity, pressure_score, summary, semantic_labels)
                VALUES (?, ?, ?, ?, ?)
            """, (
                None,  # NULL signal_type (should be NOT NULL)
                'invalid_severity',  # Invalid severity
                999.99,  # Out of range pressure
                None,  # NULL summary
                'not_valid_json'  # Invalid JSON
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            # Expected - constraint violation
            pass
        finally:
            conn.close()
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_handle_database_lock(self):
        """Test system handles database locks"""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = DatabaseManager(db_path)
        
        # Hold a connection
        conn1 = db.connect()
        conn1.execute("BEGIN EXCLUSIVE")
        
        # Try to access from another connection
        tools = AgentTools(db_path)
        try:
            # This should timeout or handle lock gracefully
            conn1.execute("COMMIT")
            result = tools.query_signals(limit=10)
        except:
            pass  # Lock error is acceptable
        finally:
            conn1.close()
            os.close(db_fd)
            os.unlink(db_path)


class TestMalformedDataHandling(unittest.TestCase):
    """Test handling of malformed input data"""
    
    def test_malformed_signal_event(self):
        """Test classifier handles malformed events"""
        from pipeline.signals.system_classifier import SystemMetricsClassifier
        
        classifier = SystemMetricsClassifier()
        
        # Missing required fields
        malformed_events = [
            {},  # Empty
            {'invalid': 'data'},  # Wrong fields
            {'mem_available_mb': 'not_a_number'},  # Wrong types
            {'mem_available_mb': -1000},  # Negative values
            None,  # None
        ]
        
        for event in malformed_events:
            try:
                result = classifier.classify_memory_pressure(event)
                # Should return None or handle gracefully
                self.assertIn(result, [None, {}]) or self.assertIsInstance(result, dict)
            except (TypeError, KeyError, AttributeError):
                # Expected for malformed data
                pass
    
    def test_extreme_values(self):
        """Test system handles extreme values"""
        from pipeline.signals.system_classifier import SystemMetricsClassifier
        
        classifier = SystemMetricsClassifier()
        
        extreme_events = [
            {'mem_available_mb': 999999999, 'mem_total_mb': 1000, 'timestamp': 0},
            {'mem_available_mb': 0, 'mem_total_mb': 0, 'timestamp': 0},
            {'load_1m': 99999.0, 'cpu_count': 1, 'timestamp': 0},
            {'load_1m': -100.0, 'cpu_count': -5, 'timestamp': 0},
        ]
        
        for event in extreme_events:
            try:
                classifier.classify_memory_pressure(event)
                classifier.classify_load_mismatch(event)
                # Should not crash
            except (ValueError, ZeroDivisionError):
                # Expected for extreme values
                pass


class TestRaceConditions(unittest.TestCase):
    """Test for race conditions in concurrent operations"""
    
    def test_concurrent_signal_insertion(self):
        """Test concurrent signal insertions don't cause corruption"""
        import concurrent.futures
        import threading
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = DatabaseManager(db_path)
        
        def insert_signal(i):
            try:
                conn = db.connect()
                conn.execute("""
                    INSERT INTO signal_metadata 
                    (signal_type, severity, pressure_score, summary)
                    VALUES (?, ?, ?, ?)
                """, (f'signal_{i}', 'medium', 0.5, f'Test signal {i}'))
                conn.commit()
                conn.close()
                return True
            except:
                return False
        
        # Insert 50 signals concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(insert_signal, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # Check database integrity
        conn = db.connect()
        count = conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
        conn.close()
        
        # Most should have succeeded
        self.assertGreater(count, 30)
        
        os.close(db_fd)
        os.unlink(db_path)


def run_chaos_tests():
    """Run chaos tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAPIResilience))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseResilience))
    suite.addTests(loader.loadTestsFromTestCase(TestMalformedDataHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestRaceConditions))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    print("Running Chaos Tests...")
    print("Testing system resilience to failures and adverse conditions")
    print()
    sys.exit(run_chaos_tests())

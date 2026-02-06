#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Integration Tests for KernelSight AI

End-to-end tests for:
- Signal ingestion pipeline
- Agent decision cycle
- API endpoints
"""

import unittest
import sys
import os
from pathlib import Path
import tempfile
import json
import time
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.db_manager import DatabaseManager
from agent.agent_tools import AgentTools
from agent.autonomous_loop import AutonomousAgent


class TestSignalPipeline(unittest.TestCase):
    """Test end-to-end signal processing pipeline"""
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = DatabaseManager(self.db_path)
    
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_signal_insertion_and_retrieval(self):
        """Test full pipeline: insert signal and retrieve it"""
        tools = AgentTools(self.db_path)
        
        # Insert test signal
        conn = self.db.connect()
        conn.execute("""
            INSERT INTO signal_metadata 
            (signal_type, severity, pressure_score, summary, semantic_labels)
            VALUES (?, ?, ?, ?, ?)
        """, ('memory_pressure', 'critical', 0.95, 'Critical memory pressure', '["memory"]'))
        conn.commit()
        conn.close()
        
        # Query signals
        result = tools.query_signals(signal_types=['memory_pressure'], limit=10)
        
        self.assertGreater(result['signal_count'], 0)
        self.assertIn('signals', result)
        self.assertEqual(result['signals'][0]['signal_type'], 'memory_pressure')
    
    def test_baseline_storage_and_retrieval(self):
        """Test baseline creation and retrieval"""
        tools = AgentTools(self.db_path)
        
        # Insert baseline
        conn = self.db.connect()
        conn.execute("""
            INSERT INTO baseline_profiles
            (signal_type, baseline_value, percentile_50, percentile_95, percentile_99, observation_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('memory_pressure', 0.3, 0.3, 0.5, 0.7, 100))
        conn.commit()
        conn.close()
        
        # Retrieve baseline
        from analysis.baseline_analyzer import BaselineAnalyzer
        analyzer = BaselineAnalyzer(self.db_path)
        baselines = analyzer.load_baselines(max_age_hours=24)
        
        self.assertGreater(len(baselines), 0)


class TestAgentDecisionCycle(unittest.TestCase):
    """Test autonomous agent decision cycle"""
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = DatabaseManager(self.db_path)
        self.agent = AutonomousAgent(self.db_path, api_key=None)
    
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_agent_handles_no_signals(self):
        """Test agent gracefully handles empty database"""
        result = self.agent.analyze_and_act(max_iterations=1)
        
        self.assertIn('status', result)
        self.assertEqual(result['status'], 'healthy')
    
    def test_agent_detects_critical_signal(self):
        """Test agent detects and responds to critical signal"""
        # Insert critical signal
        conn = self.db.connect()
        conn.execute("""
            INSERT INTO signal_metadata 
            (signal_type, severity, pressure_score, summary)
            VALUES (?, ?, ?, ?)
        """, ('memory_pressure', 'critical', 0.95, 'Critical memory pressure'))
        conn.commit()
        conn.close()
        
        # Run agent
        result = self.agent.analyze_and_act(max_iterations=1)
        
        self.assertIn('phases', result)
        self.assertIn('observe', result['phases'])


class TestAPIIntegration(unittest.TestCase):
    """Test API endpoint integration"""
    
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
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        response = requests.get('http://localhost:8000/api/health')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
    
    def test_signals_endpoint(self):
        """Test /api/signals endpoint"""
        response = requests.get('http://localhost:8000/api/signals?limit=5')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('signal_count', data)
        self.assertIn('signals', data)
    
    def test_stats_endpoint(self):
        """Test /api/stats endpoint"""
        response = requests.get('http://localhost:8000/api/stats')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_signals', data)
        self.assertIn('by_type', data)
    
    def test_agent_status_endpoint(self):
        """Test /api/agent/status endpoint"""
        response = requests.get('http://localhost:8000/api/agent/status')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
    
    def test_diagnostics_endpoint(self):
        """Test /api/diagnostics endpoint"""
        response = requests.get('http://localhost:8000/api/diagnostics')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('overall_status', data)
        self.assertIn('checks', data)


def run_integration_tests():
    """Run integration tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSignalPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentDecisionCycle))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    print("Running Integration Tests...")
    print("Note: Some tests require the API server to be running")
    print()
    sys.exit(run_integration_tests())

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Tests for feature engineering module.
"""

import os
import sys
import unittest
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'pipeline'))

from features import FeatureEngine, FeatureExporter, FEATURE_CATALOG, FeatureGroup
from features.feature_engine import RollingWindow
from db_manager import DatabaseManager


class TestFeatureDefinitions(unittest.TestCase):
    """Test feature catalog and definitions."""
    
    def test_feature_catalog_exists(self):
        """Test that feature catalog is populated."""
        self.assertGreater(len(FEATURE_CATALOG), 0)
    
    def test_feature_groups(self):
        """Test that features are organized into groups."""
        groups = set(f.group for f in FEATURE_CATALOG.values())
        self.assertIn(FeatureGroup.MEMORY, groups)
        self.assertIn(FeatureGroup.IO, groups)
        self.assertIn(FeatureGroup.NETWORK, groups)
    
    def test_feature_metadata(self):
        """Test that features have required metadata."""
        for name, feature in FEATURE_CATALOG.items():
            self.assertEqual(feature.name, name)
            self.assertIsNotNone(feature.description)
            self.assertIsNotNone(feature.formula)
            self.assertIsInstance(feature.group, FeatureGroup)


class TestRollingWindow(unittest.TestCase):
    """Test rolling window calculations."""
    
    def test_rolling_mean(self):
        """Test rolling mean calculation."""
        window = RollingWindow(window_size=3)
        
        # Add values
        window.add(10.0, 1000)
        window.add(20.0, 2000)
        window.add(30.0, 3000)
        
        self.assertAlmostEqual(window.mean(), 20.0)
    
    def test_rolling_std(self):
        """Test rolling standard deviation."""
        window = RollingWindow(window_size=3)
        
        window.add(10.0, 1000)
        window.add(20.0, 2000)
        window.add(30.0, 3000)
        
        expected_std = np.std([10, 20, 30], ddof=1)
        self.assertAlmostEqual(window.std(), expected_std)
    
    def test_get_delta(self):
        """Test delta calculation."""
        window = RollingWindow(window_size=3)
        
        window.add(10.0, 1000)
        window.add(25.0, 2000)
        
        self.assertAlmostEqual(window.get_delta(), 15.0)
    
    def test_get_rate(self):
        """Test rate calculation."""
        window = RollingWindow(window_size=3)
        
        window.add(10.0, 1_000_000_000)  # t=1s
        window.add(30.0, 2_000_000_000)  # t=2s
        
        # Rate = (30 - 10) / (2s - 1s) = 20 / 1s = 20
        self.assertAlmostEqual(window.get_rate(), 20.0)
    
    def test_window_overflow(self):
        """Test that window maintains max size."""
        window = RollingWindow(window_size=2)
        
        window.add(10.0, 1000)
        window.add(20.0, 2000)
        window.add(30.0, 3000)  # Should evict 10.0
        
        # Mean of last 2: (20 + 30) / 2 = 25
        self.assertAlmostEqual(window.mean(), 25.0)


class TestFeatureEngine(unittest.TestCase):
    """Test feature computation engine."""
    
    def setUp(self):
        """Create a temporary database with test data."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize database with schema
        db = DatabaseManager(self.temp_db.name)
        db.init_schema()
        
        # Insert test data
        base_time = int(datetime.now().timestamp() * 1_000_000_000)
        
        for i in range(10):
            timestamp = base_time + i * 1_000_000_000  # 1 second intervals
            
            # Memory metrics
            db.insert_memory_metrics({
                'timestamp': timestamp,
                'mem_total_kb': 8192000,
                'mem_available_kb': 4096000 - i * 100000,  # Decreasing
                'mem_free_kb': 2048000,
                'buffers_kb': 512000,
                'cached_kb': 2048000,
                'swap_total_kb': 4096000,
                'swap_free_kb': 4096000 - i * 10000,
                'dirty_kb': 10240,
                'writeback_kb': 0
            })
            
            # Block stats
            db.insert_block_stats({
                'timestamp': timestamp,
                'device_name': 'sda',
                'read_ios': i * 100,
                'write_ios': i * 50,
                'read_sectors': i * 1000,
                'write_sectors': i * 500,
                'read_ticks': i * 10,
                'write_ticks': i * 5,
                'in_flight': 2
            })
            
            # Network stats
            db.insert_network_stats({
                'timestamp': timestamp,
                'interface_name': 'eth0',
                'rx_bytes': i * 1000000,
                'tx_bytes': i * 500000,
                'rx_packets': i * 1000,
                'tx_packets': i * 500,
                'rx_errors': 0,
                'tx_errors': 0,
                'rx_drops': 0,
                'tx_drops': 0
            })
            
            # Load metrics
            db.insert_load_metrics({
                'timestamp': timestamp,
                'load_1min': 1.5,
                'load_5min': 1.2,
                'load_15min': 1.0,
                'running_processes': 2,
                'total_processes': 100,
                'last_pid': 1000
            })
        
        db.commit()
        db.close()
    
    def tearDown(self):
        """Clean up temporary database."""
        os.unlink(self.temp_db.name)
    
    def test_batch_compute(self):
        """Test batch feature computation."""
        engine = FeatureEngine(mode='batch', db_path=self.temp_db.name)
        
        start_time = datetime.now() - timedelta(minutes=1)
        end_time = datetime.now()
        
        features = engine.batch_compute(start_time, end_time, device='sda', interface='eth0')
        
        # Should have computed features
        self.assertIn('mem_available_mb', features)
        self.assertIn('mem_used_pct', features)
        self.assertIn('load_1min', features)
        
        # Values should be arrays
        self.assertIsInstance(features['mem_available_mb'], np.ndarray)
        
        engine.close()
    
    def test_baseline_stats(self):
        """Test baseline statistics computation."""
        engine = FeatureEngine(mode='batch', db_path=self.temp_db.name)
        
        start_time = datetime.now() - timedelta(minutes=1)
        end_time = datetime.now()
        
        features = engine.batch_compute(start_time, end_time, device='sda', interface='eth0')
        baseline = engine.get_baseline_stats()
        
        # Should have baseline for computed features
        self.assertIn('mem_available_mb', baseline)
        self.assertIn('mean', baseline['mem_available_mb'])
        self.assertIn('std', baseline['mem_available_mb'])
        
        engine.close()
    
    def test_zscore_features(self):
        """Test z-score feature computation."""
        engine = FeatureEngine(mode='batch', db_path=self.temp_db.name)
        
        start_time = datetime.now() - timedelta(minutes=1)
        end_time = datetime.now()
        
        features = engine.batch_compute(start_time, end_time, device='sda', interface='eth0')
        
        # Should have z-score features
        self.assertIn('mem_used_pct_zscore', features)
        
        # Z-scores should be finite
        zscore = features['mem_used_pct_zscore']
        self.assertTrue(np.all(np.isfinite(zscore[~np.isnan(zscore)])))
        
        engine.close()


class TestFeatureExporter(unittest.TestCase):
    """Test feature export functionality."""
    
    def setUp(self):
        """Create test features."""
        self.test_features = {
            'timestamp': np.array([1000, 2000, 3000]),
            'feature1': np.array([10.0, 20.0, 30.0]),
            'feature2': np.array([100.0, 200.0, 300.0])
        }
        
        self.temp_dir = tempfile.mkdtemp()
        self.exporter = FeatureExporter(output_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_export_csv(self):
        """Test CSV export."""
        self.exporter.export_csv(self.test_features, "test.csv")
        
        csv_path = Path(self.temp_dir) / "test.csv"
        self.assertTrue(csv_path.exists())
        
        # Check content
        with open(csv_path) as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 4)  # Header + 3 rows
            self.assertIn('timestamp', lines[0])
            self.assertIn('feature1', lines[0])
    
    def test_export_numpy(self):
        """Test NumPy export."""
        self.exporter.export_numpy(self.test_features, "test.npz")
        
        npz_path = Path(self.temp_dir) / "test.npz"
        self.assertTrue(npz_path.exists())
        
        # Load and verify
        data = np.load(npz_path)
        self.assertIn('feature_matrix', data)
        self.assertIn('feature_names', data)
        self.assertEqual(data['feature_matrix'].shape, (3, 2))  # 3 samples, 2 features
    
    def test_export_json(self):
        """Test JSON metadata export."""
        self.exporter.export_json(self.test_features, filename="test_metadata.json")
        
        json_path = Path(self.temp_dir) / "test_metadata.json"
        self.assertTrue(json_path.exists())
        
        # Load and verify
        import json
        with open(json_path) as f:
            metadata = json.load(f)
        
        self.assertIn('features', metadata)
        self.assertIn('num_samples', metadata)
        self.assertEqual(metadata['num_samples'], 3)
    
    def test_get_anomalies(self):
        """Test anomaly detection."""
        baseline = {
            'feature1': {'mean': 15.0, 'std': 5.0},
            'feature2': {'mean': 150.0, 'std': 50.0}
        }
        
        anomalies = self.exporter.get_anomalies(
            self.test_features,
            baseline,
            threshold=2.0
        )
        
        # feature1 last value = 30, z = (30-15)/5 = 3.0 > 2.0
        # feature2 last value = 300, z = (300-150)/50 = 3.0 > 2.0
        self.assertEqual(len(anomalies), 2)
        self.assertEqual(anomalies[0]['feature'], 'feature1')


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())

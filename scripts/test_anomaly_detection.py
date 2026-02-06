#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Anomaly detection test script.

Creates synthetic data with injected anomalies to validate the
feature engineering module's anomaly detection capabilities.
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'pipeline'))

from db_manager import DatabaseManager
from features import FeatureEngine, FeatureExporter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def create_test_database_with_anomalies():
    """Create a test database with normal data and injected anomalies."""
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    print(f"📊 Creating test database: {temp_db.name}")
    
    db = DatabaseManager(temp_db.name)
    db.init_schema()
    
    base_time = int(datetime.now().timestamp() * 1_000_000_000)
    
    print("\n🔧 Generating synthetic telemetry data...")
    print("   ├─ 50 normal samples")
    print("   └─ 5 anomalous samples at the end")
    
    # Generate 50 normal samples
    for i in range(50):
        timestamp = base_time + i * 1_000_000_000  # 1 second intervals
        
        # Normal memory metrics
        db.insert_memory_metrics({
            'timestamp': timestamp,
            'mem_total_kb': 8192000,
            'mem_available_kb': 4096000 + (i % 10) * 10000,  # Small variations
            'mem_free_kb': 2048000,
            'buffers_kb': 512000,
            'cached_kb': 2048000,
            'swap_total_kb': 4096000,
            'swap_free_kb': 4096000 - i * 100,  # Gradually using swap
            'dirty_kb': 10240,
            'writeback_kb': 0
        })
        
        # Normal block stats
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
        
        # Normal load metrics
        db.insert_load_metrics({
            'timestamp': timestamp,
            'load_1min': 1.0 + (i % 5) * 0.1,  # Varies 1.0-1.5
            'load_5min': 1.0,
            'load_15min': 1.0,
            'running_processes': 2,
            'total_processes': 100,
            'last_pid': 1000 + i
        })
        
        # I/O latency stats - normal
        db.insert_io_latency_stats({
            'timestamp': timestamp,
            'read_count': 100,
            'write_count': 50,
            'read_bytes': 1024000,
            'write_bytes': 512000,
            'read_p50_us': 1000,
            'read_p95_us': 2000,
            'read_p99_us': 3000,
            'read_max_us': 5000,
            'write_p50_us': 1500,
            'write_p95_us': 3000,
            'write_p99_us': 4000,
            'write_max_us': 6000
        })
    
    print("\n⚠️  Injecting ANOMALIES in last 5 samples...")
    
    # Inject 5 anomalous samples at the end
    anomaly_types = [
        "Memory spike (99% used)",
        "I/O latency spike (100ms p95)",
        "Memory pressure (high swap usage)",
        "Extreme load (10.0)",
        "Combined anomalies"
    ]
    
    for j, anomaly_desc in enumerate(anomaly_types):
        i = 50 + j
        timestamp = base_time + i * 1_000_000_000
        
        print(f"   └─ Sample {i+1}: {anomaly_desc}")
        
        # Anomaly 1: Memory spike
        mem_available = 4096000 if j != 0 else 100000  # Very low memory
        swap_free = 4096000 - 50 * 100 if j != 2 else 0  # Swap exhausted
        dirty = 10240 if j != 2 else 500000  # High dirty pages
        
        db.insert_memory_metrics({
            'timestamp': timestamp,
            'mem_total_kb': 8192000,
            'mem_available_kb': mem_available,
            'mem_free_kb': 2048000,
            'buffers_kb': 512000,
            'cached_kb': 2048000,
            'swap_total_kb': 4096000,
            'swap_free_kb': swap_free,
            'dirty_kb': dirty,
            'writeback_kb': 0
        })
        
        # Anomaly 2: I/O latency spike
        write_p95 = 3000 if j != 1 else 100000  # 100ms spike
        
        db.insert_io_latency_stats({
            'timestamp': timestamp,
            'read_count': 100,
            'write_count': 50,
            'read_bytes': 1024000,
            'write_bytes': 512000,
            'read_p50_us': 1000,
            'read_p95_us': 2000,
            'read_p99_us': 3000,
            'read_max_us': 5000,
            'write_p50_us': 1500,
            'write_p95_us': write_p95,
            'write_p99_us': 4000,
            'write_max_us': 6000
        })
        
        # Anomaly 4: Load spike
        load_1min = 1.2 if j != 3 else 10.0  # Extreme load
        
        db.insert_load_metrics({
            'timestamp': timestamp,
            'load_1min': load_1min,
            'load_5min': 1.0,
            'load_15min': 1.0,
            'running_processes': 2,
            'total_processes': 100,
            'last_pid': 1000 + i
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
    
    db.commit()
    db.close()
    
    print(f"\n✅ Test database created: {temp_db.name}")
    return temp_db.name


def test_anomaly_detection(db_path):
    """Test anomaly detection on the synthetic database."""
    
    print("\n" + "="*80)
    print(" Testing Anomaly Detection")
    print("="*80)
    
    # Initialize engine
    engine = FeatureEngine(mode='batch', db_path=db_path)
    exporter = FeatureExporter(output_dir='data/features/anomaly_test')
    
    # Query the actual time range from the database
    from db_manager import DatabaseManager
    db = DatabaseManager(db_path)
    rows = db.query("SELECT MIN(timestamp), MAX(timestamp) FROM memory_metrics")
    start_ns = rows[0][0]
    end_ns = rows[0][1]
    
    # Split into training (first 50 samples: 0-49) and test (last 5 samples: 50-54)
    # Each sample is 1 second apart, timestamps are inclusive
    train_start = datetime.fromtimestamp(start_ns / 1e9)
    train_end = datetime.fromtimestamp((start_ns + 49 * 1_000_000_000) / 1e9)  # 49 seconds = samples 0-49
    test_start = datetime.fromtimestamp((start_ns + 50 * 1_000_000_000) / 1e9)  # Start at sample 50
    test_end = datetime.fromtimestamp(end_ns / 1e9)
    
    db.close()
    
    print("\n" + "="*80)
    print(" Phase 1: Training Baseline on Normal Data")
    print("="*80)
    
    print(f"\n📅 Training range: {train_start} to {train_end}")
    print(f"⏱️  Duration: 50 seconds (normal samples)")
    
    print("\n🔄 Computing features from training data...")
    train_features = engine.batch_compute(train_start, train_end, device='sda')
    
    print(f"✅ Computed {len(train_features)} features over {len(train_features.get('timestamp', []))} samples")
    
    # Get baseline statistics from TRAINING data only
    # CRITICAL: Make a COPY because batch_compute() will overwrite it!
    import copy
    train_baseline = copy.deepcopy(engine.get_baseline_stats())
    print(f"✅ Baseline learned from {len(train_baseline)} features")
    
    # Show baseline stats for key features
    print("\n📊 Learned Baseline Statistics:")
    key_features = ['mem_used_pct', 'io_latency_write_p95', 'load_1min', 'mem_pressure']
    for feat in key_features:
        if feat in train_baseline:
            stats = train_baseline[feat]
            print(f"  {feat}:")
            print(f"    Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")
    
    print("\n" + "="*80)
    print(" Phase 2: Testing on Anomalous Data")
    print("="*80)
    
    print(f"\n📅 Test range: {test_start} to {test_end}")
    print(f"⏱️  Duration: 5 seconds (anomalous samples)")
    
    print("\n🔄 Computing features from test data...")
    test_features = engine.batch_compute(test_start, test_end, device='sda')
    
    print(f"✅ Computed {len(test_features)} features over {len(test_features.get('timestamp', []))} samples")
    
    # Detect anomalies using TRAINING baseline
    print("\n" + "="*80)
    print(" Anomaly Detection Results")
    print("="*80)
    
    print("\n🔍 Comparing test samples against learned baseline (threshold: 2.0σ)...\n")
    
    # Check each test sample
    import numpy as np
    n_test_samples = len(test_features.get('timestamp', []))
    
    all_anomalies = []
    
    for sample_idx in range(n_test_samples):
        print(f"Sample {51 + sample_idx} (Anomaly type: ", end="")
        anomaly_types = [
            "Memory spike",
            "I/O latency spike", 
            "Memory pressure",
            "Extreme load",
            "Combined"
        ]
        print(f"{anomaly_types[sample_idx]}):")
        
        sample_anomalies = []
        
        features_checked = 0
        # Check each feature against TRAINING baseline
        for feature_name, test_values in test_features.items():
            if feature_name == 'timestamp':
                continue
            
            # Skip derived z-score features (they used wrong baseline)
            if '_zscore' in feature_name:
                continue
            
            if feature_name not in train_baseline:
                continue
            
            baseline = train_baseline[feature_name]
            
            # Skip features with no variance in training
            if baseline['std'] == 0:
                continue
            
            features_checked += 1
            
            # Get value for this sample
            if sample_idx >= len(test_values):
                continue
            
            value = test_values[sample_idx]
            if not np.isfinite(value):
                continue
            
            # Compute z-score against TRAINING baseline  
            zscore = (value - baseline['mean']) / baseline['std']
            
            if abs(zscore) >= 2.0:
                sample_anomalies.append({
                    'sample': 51 + sample_idx,
                    'feature': feature_name,
                    'value': float(value),
                    'zscore': float(zscore),
                    'baseline_mean': baseline['mean'],
                    'baseline_std': baseline['std']
                })
        
        # Sort by absolute z-score
        sample_anomalies.sort(key=lambda x: abs(x['zscore']), reverse=True)
        
        if sample_anomalies:
            for anom in sample_anomalies[:3]:  # Show top 3
                severity = "🔴 CRITICAL" if abs(anom['zscore']) > 4 else "🟡 WARNING"
                print(f"  {severity} {anom['feature']}: {anom['value']:.2f} (z={anom['zscore']:.2f}σ)")
            if len(sample_anomalies) > 3:
                print(f"  ... and {len(sample_anomalies) - 3} more anomalies")
            all_anomalies.extend(sample_anomalies)
        else:
            print(f"  ✅ No anomalies detected")
        
        print()
    
    # Summary
    print("="*80)
    print(" Detection Summary")
    print("="*80)
    
    if all_anomalies:
        print(f"\n🚨 Total anomalies detected: {len(all_anomalies)}")
        print(f"📊 Across {n_test_samples} test samples")
        
        # Top anomalies overall
        all_anomalies.sort(key=lambda x: abs(x['zscore']), reverse=True)
        print(f"\n🔝 Top 5 Most Extreme Anomalies:")
        for i, anom in enumerate(all_anomalies[:5], 1):
            print(f"  {i}. Sample {anom['sample']}: {anom['feature']} = {anom['value']:.2f} (z={anom['zscore']:.2f}σ)")
    else:
        print("\n❌ No anomalies detected (unexpected!)")
    
    # Export results
    print("\n" + "="*80)
    print(" Exporting Results")
    print("="*80)
    
    exporter.export_all(train_features, train_baseline, prefix='training_baseline')
    exporter.export_all(test_features, train_baseline, prefix='test_anomalies')
    engine.save_baseline_stats('data/features/anomaly_test/baseline.json')
    
    print("\n✅ Exported to data/features/anomaly_test/:")
    print("   ├─ training_baseline.csv (normal data)")
    print("   ├─ training_baseline.npz")
    print("   ├─ test_anomalies.csv (anomalous data)")
    print("   ├─ test_anomalies.npz")
    print("   └─ baseline.json (learned from normal data)")
    
    engine.close()
    
    return len(all_anomalies) > 0


def main():
    """Main test execution."""
    print("\n" + "="*80)
    print(" KernelSight AI - Anomaly Detection Test")
    print("="*80)
    
    # Create test database with anomalies
    db_path = create_test_database_with_anomalies()
    
    # Test anomaly detection
    success = test_anomaly_detection(db_path)
    
    # Cleanup
    print("\n" + "="*80)
    print(" Test Complete")
    print("="*80)
    
    if success:
        print("\n✅ TEST PASSED: Anomalies were successfully detected!")
        print(f"\n💡 Tip: Review the exports in data/features/anomaly_test/")
        print(f"   Test database saved at: {db_path}")
        return 0
    else:
        print("\n❌ TEST FAILED: No anomalies detected (check thresholds)")
        return 1


if __name__ == '__main__':
    sys.exit(main())

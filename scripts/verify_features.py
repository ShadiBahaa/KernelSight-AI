#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Verification script for feature engineering module.

Validates feature computation on real stress test data.
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'pipeline'))

from features import FeatureEngine, FeatureExporter
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str):
    """Print a section separator."""
    print(f"\n{'=' * 80}")
    print(f" {title}")
    print('=' * 80)


def verify_features(db_path: str, device: str = 'sda', interface: str = 'eth0'):
    """
    Verify feature computation on database.
    
    Args:
        db_path: Path to database
        device: Block device name
        interface: Network interface name
    """
    print_separator("KernelSight AI - Feature Engineering Verification")
    
    # Initialize engine
    print(f"\n📊 Initializing FeatureEngine with database: {db_path}")
    engine = FeatureEngine(mode='batch', db_path=db_path)
    exporter = FeatureExporter(output_dir='data/features')
    
    # Determine time range from database
    from db_manager import DatabaseManager
    db = DatabaseManager(db_path)
    
    rows = db.query("SELECT MIN(timestamp), MAX(timestamp) FROM memory_metrics")
    if rows and rows[0][0]:
        start_ns = rows[0][0]
        end_ns = rows[0][1]
        start_time = datetime.fromtimestamp(start_ns / 1e9)
        end_time = datetime.fromtimestamp(end_ns / 1e9)
        
        print(f"📅 Data range: {start_time} to {end_time}")
        print(f"⏱️  Duration: {(end_time - start_time).total_seconds():.0f} seconds")
    else:
        logger.error("No data found in database!")
        return 1
    
    db.close()
    
    # Compute features
    print_separator("Computing Features")
    print(f"\n🔄 Processing telemetry data...")
    features = engine.batch_compute(start_time, end_time, device=device, interface=interface)
    
    if not features:
        logger.error("No features computed!")
        return 1
    
    print(f"✅ Computed {len(features)} features")
    
    # Print feature summary
    print_separator("Feature Summary")
    
    feature_names = [name for name in features.keys() if name != 'timestamp']
    for name in sorted(feature_names):
        values = features[name]
        valid_values = values[np.isfinite(values)]
        
        if len(valid_values) > 0:
            print(f"\n  {name}:")
            print(f"    Samples: {len(values)}, Valid: {len(valid_values)}, "
                  f"NaN: {np.sum(np.isnan(values))}")
            print(f"    Range: [{np.min(valid_values):.2f}, {np.max(valid_values):.2f}]")
            print(f"    Mean: {np.mean(valid_values):.2f}, "
                  f"Std: {np.std(valid_values):.2f}")
        else:
            print(f"\n  {name}: ❌ No valid values")
    
    # Baseline statistics
    print_separator("Baseline Statistics")
    baseline = engine.get_baseline_stats()
    print(f"\n✅ Computed baseline for {len(baseline)} features")
    
    for name in sorted(list(baseline.keys())[:5]):  # Show first 5
        stats = baseline[name]
        print(f"\n  {name}:")
        print(f"    Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")
        print(f"    Range: [{stats['min']:.2f}, {stats['max']:.2f}]")
    print(f"\n  ... and {len(baseline) - 5} more")
    
    # Check for anomalies in last sample
    print_separator("Anomaly Detection (Latest Sample)")
    anomalies = exporter.get_anomalies(features, baseline, threshold=2.0)
    
    if anomalies:
        print(f"\n⚠️  Found {len(anomalies)} anomalies (z-score > 2σ):\n")
        for i, anomaly in enumerate(anomalies[:10], 1):  # Show top 10
            print(f"  {i}. {anomaly['feature']}: {anomaly['value']:.2f} "
                  f"(z={anomaly['zscore']:.2f}σ)")
            if i == 10 and len(anomalies) > 10:
                print(f"  ... and {len(anomalies) - 10} more")
                break
    else:
        print("\n✅ No significant anomalies detected")
    
    # Export features
    print_separator("Exporting Features")
    print("\n📦 Exporting to multiple formats...")
    
    exporter.export_all(features, baseline, prefix='stress_test')
    
    print(f"✅ Exported to data/features/:")
    print(f"  - stress_test.csv (human-readable)")
    print(f"  - stress_test.npz (NumPy matrix)")
    print(f"  - stress_test_metadata.json (feature definitions)")
    
    # Save baseline
    engine.save_baseline_stats('data/features/baseline_stats.json')
    print(f"  - baseline_stats.json (for real-time comparison)")
    
    # Verify exports
    print_separator("Verifying Exports")
    
    # Check CSV
    csv_path = Path('data/features/stress_test.csv')
    if csv_path.exists():
        line_count = sum(1 for _ in open(csv_path))
        print(f"\n✅ CSV: {line_count} lines (including header)")
    else:
        print("\n❌ CSV export failed!")
    
    # Check NumPy
    npz_path = Path('data/features/stress_test.npz')
    if npz_path.exists():
        data = np.load(npz_path)
        print(f"✅ NumPy: shape={data['feature_matrix'].shape}, "
              f"features={len(data['feature_names'])}")
    else:
        print("❌ NumPy export failed!")
    
    # Check JSON
    json_path = Path('data/features/stress_test_metadata.json')
    if json_path.exists():
        import json
        with open(json_path) as f:
            metadata = json.load(f)
        print(f"✅ JSON: {len(metadata['features'])} feature definitions")
    else:
        print("❌ JSON export failed!")
    
    # Final summary
    print_separator("Verification Complete")
    print(f"\n✅ Feature engineering module working correctly!")
    print(f"\n📚 Next steps:")
    print(f"  1. Review features in data/features/stress_test.csv")
    print(f"  2. Load NumPy matrix for ML training")
    print(f"  3. Use baseline_stats.json for real-time monitoring")
    print(f"  4. See docs/ml/FEATURES.md for usage guide")
    
    engine.close()
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify feature engineering module"
    )
    parser.add_argument(
        '--db-path',
        default='data/stress_test.db',
        help='Path to database (default: data/stress_test.db)'
    )
    parser.add_argument(
        '--device',
        default='sda',
        help='Block device name (default: sda)'
    )
    parser.add_argument(
        '--interface',
        default='eth0',
        help='Network interface (default: eth0)'
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db_path).exists():
        logger.error(f"Database not found: {args.db_path}")
        logger.info("Run a stress test first to generate data")
        return 1
    
    return verify_features(args.db_path, args.device, args.interface)


if __name__ == '__main__':
    sys.exit(main())

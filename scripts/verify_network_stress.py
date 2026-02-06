#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
#
# Verification script for network stress test
# Validates that TCP statistics are being populated

import sys
import os

# Add src/pipeline to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'pipeline'))

from db_manager import DatabaseManager

def verify_tcp_stats(db_path='data/stress_test.db'):
    """Verify that TCP stats have been populated by network workload."""
    
    print("=" * 60)
    print("Network Stress Test Verification")
    print("=" * 60)
    print()
    
    if not os.path.exists(db_path):
        print(f"❌ ERROR: Database not found: {db_path}")
        print("   Run the stress test first: sudo ./scripts/stress_test_full.sh")
        return False
    
    db = DatabaseManager(db_path)
    
    # Get TCP stats summary
    result = db.query("""
        SELECT 
            COUNT(*) as sample_count,
            SUM(established) as total_established,
            MAX(established) as max_established,
            SUM(time_wait) as total_time_wait,
            MAX(time_wait) as max_time_wait,
            SUM(fin_wait1 + fin_wait2) as total_fin_wait,
            MAX(fin_wait1 + fin_wait2) as max_fin_wait,
            SUM(listen) as total_listen,
            AVG(listen) as avg_listen
        FROM tcp_stats
    """)
    
    if not result or len(result) == 0:
        print("❌ ERROR: No TCP stats found in database")
        db.close()
        return False
    
    row = result[0]
    
    # Handle None values (empty database)
    if row['sample_count'] is None or row['sample_count'] == 0:
        print("❌ ERROR: No TCP stats samples in database")
        print()
        print("   The tcp_stats table is empty. Possible reasons:")
        print("   1. The stress test didn't run long enough")
        print("   2. The scraper_daemon didn't start properly")
        print("   3. There was an ingestion error")
        print()
        print("   Check the logs:")
        print("   - logs/stress_test/ingestion.log")
        print("   - logs/stress_test/scraper.log")
        db.close()
        return False
    
    # Convert None to 0 for display
    total_est = row['total_established'] or 0
    max_est = row['max_established'] or 0
    total_tw = row['total_time_wait'] or 0
    max_tw = row['max_time_wait'] or 0
    total_fw = row['total_fin_wait'] or 0
    max_fw = row['max_fin_wait'] or 0
    total_lst = row['total_listen'] or 0
    avg_lst = row['avg_listen'] or 0.0
    
    print(f"TCP Stats Summary ({row['sample_count']} samples):")
    print()
    print(f"  ESTABLISHED connections:")
    print(f"    Total: {total_est:>6}")
    print(f"    Max:   {max_est:>6}")
    print()
    print(f"  TIME_WAIT connections:")
    print(f"    Total: {total_tw:>6}")
    print(f"    Max:   {max_tw:>6}")
    print()
    print(f"  FIN_WAIT connections:")
    print(f"    Total: {total_fw:>6}")
    print(f"    Max:   {max_fw:>6}")
    print()
    print(f"  LISTEN sockets:")
    print(f"    Total: {total_lst:>6}")
    print(f"    Avg:   {avg_lst:>6.1f}")
    print()
    
    # Check for network activity
    has_network_activity = (total_est > 0 or total_tw > 0 or total_fw > 0)
    
    # Show detailed stats over time
    print("-" * 60)
    print("TCP State Distribution Over Time (last 10 samples):")
    print()
    
    samples = db.query("""
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            established, time_wait, fin_wait1, fin_wait2, listen
        FROM tcp_stats
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    print(f"{'Time':<20} {'EST':>5} {'TW':>5} {'FW1':>5} {'FW2':>5} {'LST':>5}")
    print("-" * 60)
    for sample in samples:
        print(f"{sample['time']:<20} "
              f"{sample['established']:>5} "
              f"{sample['time_wait']:>5} "
              f"{sample['fin_wait1']:>5} "
              f"{sample['fin_wait2']:>5} "
              f"{sample['listen']:>5}")
    
    print()
    print("=" * 60)
    
    if has_network_activity:
        print("✅ SUCCESS: Network workload generated TCP connection activity!")
        print()
        print("   The stress test successfully created TCP connections.")
        print("   You should see non-zero values in ESTABLISHED, TIME_WAIT,")
        print("   or FIN_WAIT states above.")
        success = True
    else:
        print("⚠️  WARNING: No TCP connection activity detected")
        print()
        print("   Possible reasons:")
        print("   1. Network workload didn't run (check logs/stress_test/*.log)")
        print("   2. HTTP server failed to start (port 8080 already in use?)")
        print("   3. curl not installed or failed")
        print()
        print("   LISTEN sockets are present, which is expected.")
        print("   But ESTABLISHED/TIME_WAIT should be > 0 if network stress ran.")
        success = False
    
    print("=" * 60)
    
    db.close()
    return success

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/stress_test.db'
    success = verify_tcp_stats(db_path)
    sys.exit(0 if success else 1)

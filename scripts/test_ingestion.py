#!/usr/bin/env python3
"""
Test if the ingestion pipeline is working by manually injecting a test event.
This bypasses the file watching and directly tests the ingestion logic.
"""
import sqlite3
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, '.')

from src.pipeline.semantic_ingestion_daemon import SemanticIngestionDaemon

db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/kernelsight.db'

print("=== Ingestion Pipeline Test ===")
print(f"Database: {db_path}")

# Get current signal count
conn = sqlite3.connect(db_path)
before_count = conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
print(f"Signals before: {before_count}")

# Create daemon and inject a synthetic stress event
daemon = SemanticIngestionDaemon(db_path)

# Create a synthetic memory pressure event with current timestamp
now_ns = int(datetime.now().timestamp() * 1_000_000_000)
test_event = {
    'type': 'meminfo',
    'timestamp': now_ns,
    'data': {
        'mem_total_kb': 8000000,      # 8GB total
        'mem_available_kb': 800000,    # Only 800MB available = 90% used = HIGH PRESSURE
        'mem_free_kb': 500000,
        'buffers_kb': 100000,
        'cached_kb': 200000,
        'swap_total_kb': 2000000,
        'swap_free_kb': 1000000,
        'dirty_kb': 1000
    }
}

print(f"\nInjecting test event with 90% memory pressure...")
print(f"  Timestamp: {now_ns} ({datetime.now().isoformat()})")

daemon.process_event(test_event)
daemon.db.commit()

# Check signal count after
after_count = conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
print(f"Signals after: {after_count}")

if after_count > before_count:
    # Get the new signal
    cursor = conn.execute("""
        SELECT signal_type, severity, pressure_score, timestamp
        FROM signal_metadata 
        ORDER BY id DESC LIMIT 1
    """)
    row = cursor.fetchone()
    print(f"\n✅ SUCCESS! New signal created:")
    print(f"  Type: {row[0]}")
    print(f"  Severity: {row[1]}")
    print(f"  Pressure: {row[2]:.2f}")
    
    age_min = (now_ns - row[3]) / 1_000_000_000 / 60
    print(f"  Age: {age_min:.1f} min ago")
    
    if row[1] in ('medium', 'high', 'critical'):
        print(f"\n🎯 Signal has severity '{row[1]}' - autonomous loop WILL detect it!")
    else:
        print(f"\n⚠️  Signal has severity '{row[1]}' - autonomous loop will SKIP it (needs medium+)")
else:
    print("\n❌ FAILED: No new signal was created!")
    print("  This means the classifier didn't detect pressure from the test event.")

conn.close()
daemon.db.close()

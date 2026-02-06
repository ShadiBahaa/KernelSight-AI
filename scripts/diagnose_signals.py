#!/usr/bin/env python3
"""
Detailed diagnostic script to understand why autonomous loop doesn't detect signals.
"""
import sqlite3
import sys
from datetime import datetime

db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/kernelsight.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== Detailed Signal Diagnostic ===")
print(f"Database: {db_path}")
print(f"Current time: {datetime.now().isoformat()}")

# Get total count
count = conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
print(f"\nTotal signals: {count}")

# Get severity distribution
print("\nSeverity distribution:")
cursor = conn.execute("""
    SELECT severity, COUNT(*) as cnt
    FROM signal_metadata 
    GROUP BY severity
    ORDER BY cnt DESC
""")
for row in cursor:
    print(f"  {row['severity']}: {row['cnt']}")

# Current time in nanoseconds
now_ns = int(datetime.now().timestamp() * 1_000_000_000)
ten_min_ago_ns = now_ns - (10 * 60 * 1_000_000_000)

# Check recent signals
print("\n--- Signals in last 10 minutes (what autonomous loop sees) ---")
cursor = conn.execute("""
    SELECT signal_type, severity, pressure_score, timestamp
    FROM signal_metadata 
    WHERE timestamp >= ?
    ORDER BY timestamp DESC 
    LIMIT 20
""", (ten_min_ago_ns,))

rows = list(cursor)
print(f"Total signals in last 10 min: {len(rows)}")

# Filter to medium+
medium_plus = [r for r in rows if r['severity'] in ('medium', 'high', 'critical')]
print(f"Medium+ signals in last 10 min: {len(medium_plus)}")

if rows:
    print("\nAll recent signals:")
    for row in rows[:10]:
        ts = row['timestamp']
        age_min = (now_ns - ts) / 1_000_000_000 / 60
        score = row['pressure_score'] if row['pressure_score'] else 0
        print(f"  {row['signal_type']:20} | {row['severity']:8} | score={score:.2f} | {age_min:.1f} min ago")

# Check latest signals regardless of time
print("\n--- Latest 10 signals (any time) ---")
cursor = conn.execute("""
    SELECT signal_type, severity, pressure_score, timestamp
    FROM signal_metadata 
    ORDER BY timestamp DESC 
    LIMIT 10
""")
for row in cursor:
    ts = row['timestamp']
    age_min = (now_ns - ts) / 1_000_000_000 / 60
    score = row['pressure_score'] if row['pressure_score'] else 0
    print(f"  {row['signal_type']:20} | {row['severity']:8} | score={score:.2f} | {age_min:.1f} min ago")

# Check if timestamps are reasonable (in nanoseconds since epoch)
print("\n--- Timestamp sanity check ---")
cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM signal_metadata")
row = cursor.fetchone()
min_ts, max_ts = row[0], row[1]
if min_ts and max_ts:
    min_dt = datetime.fromtimestamp(min_ts / 1_000_000_000)
    max_dt = datetime.fromtimestamp(max_ts / 1_000_000_000)
    print(f"Oldest signal: {min_dt.isoformat()}")
    print(f"Newest signal: {max_dt.isoformat()}")
    print(f"Newest signal age: {(now_ns - max_ts) / 1_000_000_000 / 60:.1f} minutes ago")

conn.close()

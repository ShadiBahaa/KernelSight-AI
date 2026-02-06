#!/usr/bin/env python3
"""Quick script to check signal_metadata table."""
import sqlite3
import sys
from datetime import datetime

db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/kernelsight.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Get total count
count = conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
print(f"Total signals: {count}")

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

# Get latest 10
cursor = conn.execute("""
    SELECT signal_type, severity, pressure_score, timestamp
    FROM signal_metadata 
    ORDER BY timestamp DESC 
    LIMIT 10
""")

print("\nLatest 10 signals:")
now_ns = int(datetime.now().timestamp() * 1_000_000_000)
for row in cursor:
    ts = row['timestamp']
    age_min = (now_ns - ts) / 1_000_000_000 / 60
    score = row['pressure_score'] if row['pressure_score'] else 0
    print(f"  {row['signal_type']:20} | {row['severity']:8} | score={score:.2f} | {age_min:.1f} min ago")

# Check if signals in last 10 minutes - ANY severity
ten_min_ago = now_ns - (10 * 60 * 1_000_000_000)
recent_all = conn.execute(
    "SELECT COUNT(*) FROM signal_metadata WHERE timestamp >= ?",
    (ten_min_ago,)
).fetchone()[0]
recent_medium = conn.execute(
    "SELECT COUNT(*) FROM signal_metadata WHERE timestamp >= ? AND severity IN ('medium', 'high', 'critical')",
    (ten_min_ago,)
).fetchone()[0]
print(f"\nSignals in last 10 min (ALL): {recent_all}")
print(f"Signals in last 10 min (medium+): {recent_medium}")

# Show recent with any severity
if recent_all > 0:
    print("\nRecent signals (last 10 min):")
    cursor = conn.execute("""
        SELECT signal_type, severity, pressure_score, timestamp
        FROM signal_metadata 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC 
        LIMIT 5
    """, (ten_min_ago,))
    for row in cursor:
        ts = row['timestamp']
        age_min = (now_ns - ts) / 1_000_000_000 / 60
        score = row['pressure_score'] if row['pressure_score'] else 0
        print(f"  {row['signal_type']:20} | {row['severity']:8} | score={score:.2f} | {age_min:.1f} min ago")

conn.close()

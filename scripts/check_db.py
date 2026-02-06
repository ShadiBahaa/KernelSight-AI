#!/usr/bin/env python3
"""Quick database check script."""
import sqlite3
import sys

DB_PATH = '/mnt/c/KernelSight AI/data/kernelsight.db'

try:
    conn = sqlite3.connect(DB_PATH)
    print(f"Database: {DB_PATH}\n")
    
    # Get all tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    
    print("Table row counts:")
    print("-" * 40)
    
    for (table_name,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  {table_name}: {count:,} rows")
    
    print("\n" + "=" * 40)
    
    # Sample from key tables
    print("\nRecent syscall_events (last 3):")
    rows = conn.execute(
        "SELECT timestamp, pid, syscall_name, latency_ns, comm FROM syscall_events ORDER BY id DESC LIMIT 3"
    ).fetchall()
    for row in rows:
        print(f"  {row}")
    
    print("\nRecent signal_metadata (last 5):")
    rows = conn.execute(
        "SELECT id, signal_type, scope_type, semantic_summary FROM signal_metadata ORDER BY id DESC LIMIT 5"
    ).fetchall()
    for row in rows:
        print(f"  id={row[0]}, type={row[1]}, scope={row[2]}")
        print(f"    summary: {row[3][:80] if row[3] else 'None'}...")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

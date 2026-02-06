#!/usr/bin/env python3
"""Verify the pipeline test database."""

import sys
sys.path.insert(0, 'src/pipeline')

from db_manager import DatabaseManager

db = DatabaseManager('data/test_pipeline.db')

print("=== Database Verification ===\n")

# Show table stats
stats = db.get_table_stats()
total = sum(v for v in stats.values() if v > 0)

print(f"Total events across all tables: {total}\n")
print("Events by table:")
for table, count in sorted(stats.items()):
    if count > 0:
        print(f"  {table:30} {count:6} rows")

# Sample some data
print("\n=== Sample Data ===\n")

# Sample syscall events
print("Sample Syscall Events:")
rows = db.query("SELECT * FROM syscall_events ORDER BY latency_ns DESC LIMIT 3")
for row in rows:
    print(f"  PID {row['pid']:5} | {row['comm']:10} | {row['syscall_name']:10} | "
          f"{row['latency_ns']/1e6:.2f}ms | ret={row['ret_value']}")

# Sample memory metrics
print("\nSample Memory Metrics:")
rows = db.query("SELECT * FROM memory_metrics ORDER BY timestamp DESC LIMIT 3")
for row in rows:
    used_pct = 100 - (row['mem_available_kb'] / row['mem_total_kb'] * 100)
    print(f"  Available: {row['mem_available_kb']/1024:.0f}MB | Used: {used_pct:.1f}% | "
          f"Swap Used: {(row['swap_total_kb']-row['swap_free_kb'])/1024:.0f}MB")

# Sample I/O stats
print("\nSample I/O Latency Stats:")
rows = db.query("SELECT * FROM io_latency_stats ORDER BY timestamp DESC LIMIT 3")
for row in rows:
    print(f"  Reads: {row['read_count']:4} ({row['read_bytes']/1024/1024:.1f}MB) | "
          f"Writes: {row['write_count']:4} ({row['write_bytes']/1024/1024:.1f}MB)")
    print(f"    Read P95: {row['read_p95_us']:.1f}us | Write P95: {row['write_p95_us']:.1f}us")

db.close()

print("\n✓ Database verification complete!")

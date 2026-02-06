#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Performance Benchmark Suite

Benchmarks:
- eBPF overhead measurement
- SQL query performance
- End-to-end latency
- Agent decision cycle timing
- API endpoint response times
"""

import sys
import os
import time
import sqlite3
from pathlib import Path
from typing import Dict, List
import statistics
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.db_manager import DatabaseManager
from agent.agent_tools import AgentTools


class PerformanceBenchmark:
    """Performance benchmarking suite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = DatabaseManager(db_path)
        self.tools = AgentTools(db_path)
        self.results = {}
    
    def benchmark_sql_queries(self, iterations: int = 100) -> Dict:
        """Benchmark SQL query performance"""
        print(f"\n📊 Benchmarking SQL Queries ({iterations} iterations)...")
        
        conn = self.db.connect()
        times = {}
        
        # Query 1: Count all signals
        query1_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()
            query1_times.append(time.perf_counter() - start)
        
        # Query 2: Recent signals with filter
        query2_times = []
        cutoff = (time.time() - 300) * 1_000_000_000
        for _ in range(iterations):
            start = time.perf_counter()
            conn.execute("""
                SELECT * FROM signal_metadata 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC 
                LIMIT 20
            """, (cutoff,)).fetchall()
            query2_times.append(time.perf_counter() - start)
        
        # Query 3: Aggregate by type
        query3_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            conn.execute("""
                SELECT signal_type, COUNT(*), AVG(pressure_score)
                FROM signal_metadata
                GROUP BY signal_type
            """).fetchall()
            query3_times.append(time.perf_counter() - start)
        
        conn.close()
        
        results = {
            'count_query': {
                'mean_ms': statistics.mean(query1_times) * 1000,
                'median_ms': statistics.median(query1_times) * 1000,
                'p95_ms': statistics.quantiles(query1_times, n=20)[18] * 1000,
                'p99_ms': statistics.quantiles(query1_times, n=100)[98] * 1000,
            },
            'filtered_query': {
                'mean_ms': statistics.mean(query2_times) * 1000,
                'median_ms': statistics.median(query2_times) * 1000,
                'p95_ms': statistics.quantiles(query2_times, n=20)[18] * 1000,
                'p99_ms': statistics.quantiles(query2_times, n=100)[98] * 1000,
            },
            'aggregate_query': {
                'mean_ms': statistics.mean(query3_times) * 1000,
                'median_ms': statistics.median(query3_times) * 1000,
                'p95_ms': statistics.quantiles(query3_times, n=20)[18] * 1000,
                'p99_ms': statistics.quantiles(query3_times, n=100)[98] * 1000,
            }
        }
        
        # Print results
        print(f"  COUNT query:     {results['count_query']['mean_ms']:.3f}ms avg, "
              f"{results['count_query']['p95_ms']:.3f}ms p95")
        print(f"  FILTERED query:  {results['filtered_query']['mean_ms']:.3f}ms avg, "
              f"{results['filtered_query']['p95_ms']:.3f}ms p95")
        print(f"  AGGREGATE query: {results['aggregate_query']['mean_ms']:.3f}ms avg, "
              f"{results['aggregate_query']['p95_ms']:.3f}ms p95")
        
        return results
    
    def benchmark_agent_tools(self, iterations: int = 50) -> Dict:
        """Benchmark agent tool performance"""
        print(f"\n🤖 Benchmarking Agent Tools ({iterations} iterations)...")
        
        times = {}
        
        # Query signals
        query_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            self.tools.query_signals(limit=20, lookback_minutes=10)
            query_times.append(time.perf_counter() - start)
        
        times['query_signals'] = {
            'mean_ms': statistics.mean(query_times) * 1000,
            'p95_ms': statistics.quantiles(query_times, n=20)[18] * 1000,
        }
        
        print(f"  query_signals(): {times['query_signals']['mean_ms']:.2f}ms avg, "
              f"{times['query_signals']['p95_ms']:.2f}ms p95")
        
        return times
    
    def benchmark_database_operations(self, test_size: int = 1000) -> Dict:
        """Benchmark database write performance"""
        print(f"\n💾 Benchmarking Database Operations ({test_size} inserts)...")
        
        conn = self.db.connect()
        
        # Single inserts
        start = time.perf_counter()
        for i in range(test_size):
            conn.execute("""
                INSERT INTO signal_metadata 
                (signal_type, severity, pressure_score, summary)
                VALUES (?, ?, ?, ?)
            """, (f'benchmark_signal', 'medium', 0.5, f'Test {i}'))
        conn.commit()
        single_time = time.perf_counter() - start
        
        # Clean up
        conn.execute("DELETE FROM signal_metadata WHERE signal_type = 'benchmark_signal'")
        conn.commit()
        
        # Batch inserts
        batch_data = [
            (f'benchmark_signal', 'medium', 0.5, f'Test {i}')
            for i in range(test_size)
        ]
        
        start = time.perf_counter()
        conn.executemany("""
            INSERT INTO signal_metadata 
            (signal_type, severity, pressure_score, summary)
            VALUES (?, ?, ?, ?)
        """, batch_data)
        conn.commit()
        batch_time = time.perf_counter() - start
        
        # Clean up
        conn.execute("DELETE FROM signal_metadata WHERE signal_type = 'benchmark_signal'")
        conn.commit()
        conn.close()
        
        results = {
            'single_inserts': {
                'total_time_s': single_time,
                'ops_per_sec': test_size / single_time,
                'ms_per_op': (single_time / test_size) * 1000,
            },
            'batch_inserts': {
                'total_time_s': batch_time,
                'ops_per_sec': test_size / batch_time,
                'ms_per_op': (batch_time / test_size) * 1000,
            }
        }
        
        print(f"  Single inserts: {results['single_inserts']['ops_per_sec']:.0f} ops/sec, "
              f"{results['single_inserts']['ms_per_op']:.3f}ms per op")
        print(f"  Batch inserts:  {results['batch_inserts']['ops_per_sec']:.0f} ops/sec, "
              f"{results['batch_inserts']['ms_per_op']:.3f}ms per op")
        print(f"  Speedup: {results['batch_inserts']['ops_per_sec'] / results['single_inserts']['ops_per_sec']:.1f}x")
        
        return results
    
    def measure_memory_usage(self) -> Dict:
        """Measure memory usage of key components"""
        print(f"\n💭 Measuring Memory Usage...")
        
        import psutil
        process = psutil.Process()
        
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Load some data
        conn = self.db.connect()
        data = conn.execute("SELECT * FROM signal_metadata LIMIT 10000").fetchall()
        conn.close()
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        
        results = {
            'process_rss_mb': mem_after,
            'data_loaded_mb': mem_after - mem_before,
            'records_loaded': len(data),
        }
        
        print(f"  Process RSS: {results['process_rss_mb']:.1f} MB")
        print(f"  Data loaded: {results['data_loaded_mb']:.1f} MB for {results['records_loaded']} records")
        
        return results
    
    def run_all_benchmarks(self) -> Dict:
        """Run all performance benchmarks"""
        print("="*60)
        print("  KernelSight AI - Performance Benchmark Suite")
        print("="*60)
        
        results = {}
        
        try:
            results['sql_queries'] = self.benchmark_sql_queries(iterations=100)
        except Exception as e:
            print(f"  ⚠️  SQL benchmark failed: {e}")
            results['sql_queries'] = {'error': str(e)}
        
        try:
            results['agent_tools'] = self.benchmark_agent_tools(iterations=50)
        except Exception as e:
            print(f"  ⚠️  Agent tools benchmark failed: {e}")
            results['agent_tools'] = {'error': str(e)}
        
        try:
            results['database_ops'] = self.benchmark_database_operations(test_size=1000)
        except Exception as e:
            print(f"  ⚠️  Database benchmark failed: {e}")
            results['database_ops'] = {'error': str(e)}
        
        try:
            results['memory'] = self.measure_memory_usage()
        except Exception as e:
            print(f"  ⚠️  Memory measurement failed: {e}")
            results['memory'] = {'error': str(e)}
        
        print("\n" + "="*60)
        print("  Benchmark Complete!")
        print("="*60)
        
        return results
    
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to {filename}")


def main():
    """Run performance benchmarks"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KernelSight AI Performance Benchmarks")
    parser.add_argument('--db', type=str, default='data/kernelsight.db',
                       help='Database path')
    parser.add_argument('--output', type=str, default='benchmark_results.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        print(f"❌ Database not found: {args.db}")
        print("   Run the system first: sudo python3 run_kernelsight.py")
        return 1
    
    benchmark = PerformanceBenchmark(args.db)
    results = benchmark.run_all_benchmarks()
    benchmark.results = results
    benchmark.save_results(args.output)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

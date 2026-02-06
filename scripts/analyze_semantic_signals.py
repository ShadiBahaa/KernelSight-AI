#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Semantic Signal Analysis and Visualization

Analyzes semantic signals from stress test and generates comprehensive reports with plots.
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path for any imports if needed
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter
import numpy as np


class SemanticSignalAnalyzer:
    """Analyze and visualize semantic signals from database."""
    
    def __init__(self, db_path: str, output_dir: str = "reports/semantic_analysis"):
        """
        Initialize analyzer.
        
        Args:
            db_path: Path to SQLite database
            output_dir: Output directory for reports and plots
        """
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def get_signal_stats(self):
        """Get overall signal statistics."""
        stats = {}
        
        # Total signals
        stats['total_signals'] = self.conn.execute(
            "SELECT COUNT(*) FROM signal_metadata"
        ).fetchone()[0]
        
        # Signals by type
        stats['by_type'] = dict(self.conn.execute(
            "SELECT signal_type, COUNT(*) FROM signal_metadata GROUP BY signal_type"
        ).fetchall())
        
        # Signals by severity
        stats['by_severity'] = dict(self.conn.execute(
            "SELECT severity, COUNT(*) FROM signal_metadata GROUP BY severity"
        ).fetchall())
        
        # Signals by category
        stats['by_category'] = dict(self.conn.execute(
            "SELECT signal_category, COUNT(*) FROM signal_metadata GROUP BY signal_category"
        ).fetchall())
        
        # Raw event counts
        tables = ['syscall_events', 'sched_events', 'memory_metrics', 'load_metrics',
                 'io_latency_stats', 'block_stats', 'network_interface_stats', 
                 'tcp_stats', 'page_fault_events']
        
        stats['raw_events'] = {}
        for table in tables:
            try:
                count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats['raw_events'][table] = count
            except:
                stats['raw_events'][table] = 0
        
        return stats
    
    def plot_signal_timeline(self):
        """Plot signal occurrence over time."""
        query = """
        SELECT 
            timestamp / 1000000000 as unix_time,
            signal_type,
            severity
        FROM signal_metadata
        ORDER BY timestamp
        """
        
        rows = self.conn.execute(query).fetchall()
        if not rows:
            print("No signals to plot")
            return
        
        # Convert to datetime
        times = [datetime.fromtimestamp(row['unix_time']) for row in rows]
        types = [row['signal_type'] for row in rows]
        severities = [row['severity'] for row in rows]
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Plot 1: Signals over time colored by severity
        severity_colors = {
            'critical': 'red',
            'high': 'orange',
            'medium': 'yellow',
            'low': 'green'
        }
        
        for severity in ['critical', 'high', 'medium', 'low']:
            severity_times = [t for t, s in zip(times, severities) if s == severity]
            if severity_times:
                ax1.scatter(severity_times, [severity] * len(severity_times),
                           c=severity_colors[severity], label=severity, s=100, alpha=0.7)
        
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Severity')
        ax1.set_title('Signal Timeline by Severity')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Plot 2: Signals by type over time
        unique_types = list(set(types))
        type_colors = plt.cm.tab10(np.linspace(0, 1, len(unique_types)))
        
        for signal_type, color in zip(unique_types, type_colors):
            type_times = [t for t, ty in zip(times, types) if ty == signal_type]
            if type_times:
                ax2.scatter(type_times, [signal_type] * len(type_times),
                           c=[color], label=signal_type, s=80, alpha=0.7)
        
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Signal Type')
        ax2.set_title('Signal Timeline by Type')
        ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'signal_timeline.png', dpi=150, bbox_inches='tight')
        print(f"  ✓ Timeline plot saved: {self.output_dir / 'signal_timeline.png'}")
        plt.close()
    
    def plot_signal_distribution(self):
        """Plot signal distribution by type and severity."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        
        # Plot 1: Signal count by type
        query = "SELECT signal_type, COUNT(*) as count FROM signal_metadata GROUP BY signal_type ORDER BY count DESC"
        rows = self.conn.execute(query).fetchall()
        
        types = [row['signal_type'] for row in rows]
        counts = [row['count'] for row in rows]
        
        ax1.barh(types, counts, color='steelblue')
        ax1.set_xlabel('Count')
        ax1.set_title('Signals by Type')
        ax1.grid(True, alpha=0.3, axis='x')
        
        # Plot 2: Signal count by severity
        query = "SELECT severity, COUNT(*) as count FROM signal_metadata GROUP BY severity"
        rows = self.conn.execute(query).fetchall()
        
        severity_order = ['critical', 'high', 'medium', 'low']
        severity_colors = {'critical': 'red', 'high': 'orange', 'medium': 'yellow', 'low': 'green'}
        
        sev_dict = {row['severity']: row['count'] for row in rows}
        severities = [s for s in severity_order if s in sev_dict]
        counts = [sev_dict[s] for s in severities]
        colors = [severity_colors[s] for s in severities]
        
        ax2.pie(counts, labels=severities, colors=colors, autopct='%1.1f%%', startangle=90)
        ax2.set_title('Signals by Severity')
        
        # Plot 3: Signal category distribution
        query = "SELECT signal_category, COUNT(*) as count FROM signal_metadata GROUP BY signal_category"
        rows = self.conn.execute(query).fetchall()
        
        categories = [row['signal_category'] for row in rows]
        counts = [row['count'] for row in rows]
        cat_colors = {'symptom': 'red', 'context': 'blue', 'baseline': 'green'}
        colors = [cat_colors.get(c, 'gray') for c in categories]
        
        ax3.bar(categories, counts, color=colors, alpha=0.7)
        ax3.set_ylabel('Count')
        ax3.set_title('Signals by Category')
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Plot 4: Heatmap of type vs severity
        query = """
        SELECT signal_type, severity, COUNT(*) as count 
        FROM signal_metadata 
        GROUP BY signal_type, severity
        """
        rows = self.conn.execute(query).fetchall()
        
        # Build heatmap data
        unique_types = sorted(set(row['signal_type'] for row in rows))
        heatmap_data = np.zeros((len(severity_order), len(unique_types)))
        
        for row in rows:
            type_idx = unique_types.index(row['signal_type'])
            try:
                sev_idx = severity_order.index(row['severity'])
                heatmap_data[sev_idx, type_idx] = row['count']
            except ValueError:
                pass
        
        im = ax4.imshow(heatmap_data, cmap='YlOrRd', aspect='auto')
        ax4.set_xticks(range(len(unique_types)))
        ax4.set_yticks(range(len(severity_order)))
        ax4.set_xticklabels(unique_types, rotation=45, ha='right')
        ax4.set_yticklabels(severity_order)
        ax4.set_title('Signal Type vs Severity Heatmap')
        
        # Add count labels
        for i in range(len(severity_order)):
            for j in range(len(unique_types)):
                if heatmap_data[i, j] > 0:
                    text = ax4.text(j, i, int(heatmap_data[i, j]),
                                   ha="center", va="center", color="black", fontsize=8)
        
        plt.colorbar(im, ax=ax4)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'signal_distribution.png', dpi=150, bbox_inches='tight')
        print(f"  ✓ Distribution plot saved: {self.output_dir / 'signal_distribution.png'}")
        plt.close()
    
    def plot_compression_ratio(self):
        """Plot raw events vs semantic signals (compression ratio)."""
        stats = self.get_signal_stats()
        
        total_raw = sum(stats['raw_events'].values())
        total_signals = stats['total_signals']
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Raw events by table
        tables = list(stats['raw_events'].keys())
        counts = list(stats['raw_events'].values())
        
        ax1.barh(tables, counts, color='lightcoral')
        ax1.set_xlabel('Event Count')
        ax1.set_title(f'Raw Events by Table (Total: {total_raw:,})')
        ax1.grid(True, alpha=0.3, axis='x')
        
        # Plot 2: Compression visualization
        categories = ['Raw Events', 'Semantic Signals']
        values = [total_raw, total_signals]
        colors = ['lightcoral', 'lightgreen']
        
        bars = ax2.bar(categories, values, color=colors, alpha=0.7)
        ax2.set_ylabel('Count')
        ax2.set_title(f'Compression Ratio: {total_signals/total_raw*100:.2f}%')
        ax2.set_yscale('log')
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Add count labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{val:,}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'compression_ratio.png', dpi=150, bbox_inches='tight')
        print(f"  ✓ Compression plot saved: {self.output_dir / 'compression_ratio.png'}")
        plt.close()
    
    def generate_report(self):
        """Generate comprehensive text report."""
        stats = self.get_signal_stats()
        
        report = []
        report.append("=" * 70)
        report.append("SEMANTIC SIGNAL ANALYSIS REPORT")
        report.append("=" * 70)
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Database: {self.db_path}\n")
        
        # Overview
        report.append("\n" + "=" * 70)
        report.append("OVERVIEW")
        report.append("=" * 70)
        total_raw = sum(stats['raw_events'].values())
        report.append(f"Total Raw Events:      {total_raw:,}")
        report.append(f"Total Semantic Signals: {stats['total_signals']:,}")
        report.append(f"Compression Ratio:      {stats['total_signals']/total_raw*100:.2f}%")
        
        # Raw events
        report.append("\n" + "=" * 70)
        report.append("RAW EVENT COUNTS")
        report.append("=" * 70)
        for table, count in sorted(stats['raw_events'].items(), key=lambda x: -x[1]):
            report.append(f"  {table:30s}: {count:>10,}")
        
        # Signals by type
        report.append("\n" + "=" * 70)
        report.append("SEMANTIC SIGNALS BY TYPE")
        report.append("=" * 70)
        for sig_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
            pct = count / stats['total_signals'] * 100
            report.append(f"  {sig_type:20s}: {count:>6,} ({pct:>5.1f}%)")
        
        # Signals by severity
        report.append("\n" + "=" * 70)
        report.append("SEMANTIC SIGNALS BY SEVERITY")
        report.append("=" * 70)
        severity_order = ['critical', 'high', 'medium', 'low']
        for severity in severity_order:
            count = stats['by_severity'].get(severity, 0)
            if count > 0:
                pct = count / stats['total_signals'] * 100
                report.append(f"  {severity.upper():10s}: {count:>6,} ({pct:>5.1f}%)")
        
        # Signals by category
        report.append("\n" + "=" * 70)
        report.append("SEMANTIC SIGNALS BY CATEGORY")
        report.append("=" * 70)
        for category, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
            pct = count / stats['total_signals'] * 100
            report.append(f"  {category:10s}: {count:>6,} ({pct:>5.1f}%)")
        
        # Top critical/high signals
        report.append("\n" + "=" * 70)
        report.append("TOP CRITICAL/HIGH SEVERITY SIGNALS")
        report.append("=" * 70)
        query = """
        SELECT 
            datetime(timestamp/1000000000, 'unixepoch') as time,
            signal_type,
            severity,
            summary
        FROM signal_metadata
        WHERE severity IN ('critical', 'high')
        ORDER BY 
            CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 END,
            timestamp DESC
        LIMIT 10
        """
        
        rows = self.conn.execute(query).fetchall()
        for i, row in enumerate(rows, 1):
            report.append(f"\n{i}. [{row['severity'].upper()}] {row['signal_type']} @ {row['time']}")
            report.append(f"   {row['summary']}")
        
        # Save report
        report_text = "\n".join(report)
        report_file = self.output_dir / 'analysis_report.txt'
        with open(report_file, 'w') as f:
            f.write(report_text)
        
        print(f"  ✓ Report saved: {report_file}")
        return report_text
    
    def analyze(self):
        """Run complete analysis."""
        print("\n" + "=" * 70)
        print("SEMANTIC SIGNAL ANALYSIS")
        print("=" * 70)
        
        stats = self.get_signal_stats()
        
        if stats['total_signals'] == 0:
            print("\n❌ No semantic signals found in database!")
            print("   This could mean:")
            print("   - Test duration was too short")
            print("   - System was idle (no anomalies detected)")
            print("   - Semantic ingestion daemon didn't run")
            return
        
        print(f"\nAnalyzing {stats['total_signals']:,} semantic signals...")
        print(f"Output directory: {self.output_dir}\n")
        
        # Generate plots
        try:
            print("Generating visualizations:")
            self.plot_signal_timeline()
            self.plot_signal_distribution()
            self.plot_compression_ratio()
        except Exception as e:
            print(f"⚠️  Warning: Could not generate plots: {e}")
            print("   (matplotlib may not be available)")
        
        # Generate report
        print("\nGenerating text report:")
        report = self.generate_report()
        
        print("\n" + "=" * 70)
        print("✅ ANALYSIS COMPLETE!")
        print("=" * 70)
        print(f"\nOutput files:")
        print(f"  - {self.output_dir / 'signal_timeline.png'}")
        print(f"  - {self.output_dir / 'signal_distribution.png'}")
        print(f"  - {self.output_dir / 'compression_ratio.png'}")
        print(f"  - {self.output_dir / 'analysis_report.txt'}")
        
        # Print summary
        print("\n" + "=" * 70)
        print("QUICK SUMMARY")
        print("=" * 70)
        total_raw = sum(stats['raw_events'].values())
        print(f"Raw Events:        {total_raw:,}")
        print(f"Semantic Signals:  {stats['total_signals']:,}")
        print(f"Compression:       {stats['total_signals']/total_raw*100:.2f}%")
        print(f"\nTop signal types:")
        for sig_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1])[:5]:
            print(f"  - {sig_type}: {count}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze semantic signals from stress test')
    parser.add_argument('db_path', nargs='?', default='data/semantic_stress_test.db',
                       help='Path to database file')
    parser.add_argument('--output', '-o', default='reports/semantic_analysis',
                       help='Output directory for reports')
    
    args = parser.parse_args()
    
    if not Path(args.db_path).exists():
        print(f"❌ Error: Database not found: {args.db_path}")
        print("\nRun the semantic stress test first:")
        print("  sudo ./scripts/semantic_stress_test.sh")
        sys.exit(1)
    
    analyzer = SemanticSignalAnalyzer(args.db_path, args.output)
    analyzer.analyze()


if __name__ == '__main__':
    main()

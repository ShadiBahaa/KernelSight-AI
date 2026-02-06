#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Baseline Analyzer - Extract system behavioral baselines from semantic signals.

This module analyzes signal history to establish normal operating ranges,
patterns, and volatility metrics. These baselines provide contextual grounding
for Gemini 3's autonomous reasoning.

Key Concept: We don't train ML models - we extract descriptive statistics
that represent "normal" system behavior.
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class BaselineAnalyzer:
    """Extracts and manages system behavioral baselines from signals."""
    
    def __init__(self, db_path: str):
        """
        Initialize baseline analyzer.
        
        Args:
            db_path: Path to SQLite database with signal_metadata
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def extract_signal_baselines(self, lookback_days: int = 7) -> Dict:
        """
        Extract baseline statistics for each signal type.
        
        Args:
            lookback_days: How many days of history to analyze
            
        Returns:
            Dict mapping signal_type -> baseline statistics
        """
        since_timestamp = self._get_lookback_timestamp(lookback_days)
        
        # Get all signals in lookback window
        query = """
            SELECT signal_type, severity, pressure_score, timestamp
            FROM signal_metadata
            WHERE timestamp >= ?
            ORDER BY signal_type, timestamp
        """
        
        cursor = self.conn.execute(query, (since_timestamp,))
        rows = cursor.fetchall()
        
        if not rows:
            logger.warning("No signals found in lookback window")
            return {}
        
        # Group by signal type
        signals_by_type = defaultdict(list)
        for row in rows:
            signals_by_type[row['signal_type']].append({
                'severity': row['severity'],
                'pressure_score': row['pressure_score'],
                'timestamp': row['timestamp']
            })
        
        # Extract baselines for each type
        baselines = {}
        for signal_type, signals in signals_by_type.items():
            baselines[signal_type] = self._calculate_baseline(
                signal_type, signals, lookback_days
            )
        
        logger.info(f"Extracted baselines for {len(baselines)} signal types")
        return baselines
    
    def _calculate_baseline(self, signal_type: str, signals: List[Dict], 
                           lookback_days: int) -> Dict:
        """
        Calculate baseline statistics for a single signal type.
        
        Args:
            signal_type: Type of signal
            signals: List of signal observations
            lookback_days: Analysis window
            
        Returns:
            Baseline statistics dict
        """
        # Extract pressure scores (filter out None)
        scores = [s['pressure_score'] for s in signals if s['pressure_score'] is not None]
        
        if not scores:
            return self._empty_baseline(signal_type, lookback_days)
        
        # Calculate statistical baseline
        baseline = {
            'signal_type': signal_type,
            'lookback_days': lookback_days,
            'sample_count': len(signals),
            'last_updated': int(datetime.now().timestamp() * 1_000_000_000),
            
            # Range statistics
            'normal_range': {
                'min': min(scores),
                'max': max(scores),
                'median': statistics.median(scores),
                'p25': self._percentile(scores, 25),
                'p75': self._percentile(scores, 75),
                'p95': self._percentile(scores, 95),
                'p99': self._percentile(scores, 99) if len(scores) > 10 else max(scores)
            },
            
            # Volatility measures
            'volatility': self._calculate_volatility(scores),
            
            # Severity distribution
            'severity_distribution': self._calculate_severity_dist(signals),
            
            # Temporal patterns
            'temporal_pattern': self._detect_temporal_pattern(signals),
            
            # Trend
            'trend': self._detect_trend(signals)
        }
        
        return baseline
    
    def _empty_baseline(self, signal_type: str, lookback_days: int) -> Dict:
        """Create empty baseline for signals with no pressure scores."""
        return {
            'signal_type': signal_type,
            'lookback_days': lookback_days,
            'sample_count': 0,
            'last_updated': int(datetime.now().timestamp() * 1_000_000_000),
            'normal_range': None,
            'volatility': 'unknown',
            'severity_distribution': {},
            'temporal_pattern': 'insufficient_data',
            'trend': 'unknown'
        }
    
    def _percentile(self, values: List[float], p: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * p / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    def _calculate_volatility(self, scores: List[float]) -> str:
        """
        Calculate volatility classification.
        
        Returns:
            'low', 'medium', 'high', or 'very_high'
        """
        if len(scores) < 2:
            return 'unknown'
        
        mean = statistics.mean(scores)
        if mean == 0:
            return 'unknown'
        
        stdev = statistics.stdev(scores)
        cv = stdev / mean  # Coefficient of variation
        
        # Classify volatility
        if cv < 0.2:
            return 'low'
        elif cv < 0.5:
            return 'medium'
        elif cv < 1.0:
            return 'high'
        else:
            return 'very_high'
    
    def _calculate_severity_dist(self, signals: List[Dict]) -> Dict[str, int]:
        """Calculate distribution of severity levels."""
        distribution = defaultdict(int)
        for signal in signals:
            severity = signal['severity']
            if severity:
                distribution[severity] += 1
        return dict(distribution)
    
    def _detect_temporal_pattern(self, signals: List[Dict]) -> str:
        """
        Detect temporal patterns in signal occurrence.
        
        Returns:
            Pattern classification: 'constant', 'periodic', 'sporadic', 'burst'
        """
        if len(signals) < 10:
            return 'insufficient_data'
        
        # Calculate inter-arrival times
        timestamps = sorted([s['timestamp'] for s in signals])
        intervals = []
        for i in range(1, len(timestamps)):
            delta_ns = timestamps[i] - timestamps[i-1]
            delta_sec = delta_ns / 1_000_000_000
            intervals.append(delta_sec)
        
        if not intervals:
            return 'unknown'
        
        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return 'constant'
        
        stdev_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
        cv = stdev_interval / mean_interval
        
        # Classify pattern
        if cv < 0.3:
            return 'constant'  # Regular intervals
        elif cv < 0.7:
            return 'periodic'  # Some regularity
        elif cv < 1.5:
            return 'sporadic'  # Irregular but distributed
        else:
            return 'burst'     # Clustered occurrences
    
    def _detect_trend(self, signals: List[Dict]) -> str:
        """
        Detect trend in pressure scores over time.
        
        Returns:
            'stable', 'increasing', 'decreasing', or 'unknown'
        """
        if len(signals) < 10:
            return 'unknown'
        
        # Get scores with valid pressure_score
        time_series = [(s['timestamp'], s['pressure_score']) 
                       for s in signals if s['pressure_score'] is not None]
        
        if len(time_series) < 10:
            return 'unknown'
        
        # Simple linear regression slope
        scores = [ts[1] for ts in time_series]
        first_half_mean = statistics.mean(scores[:len(scores)//2])
        second_half_mean = statistics.mean(scores[len(scores)//2:])
        
        change_pct = (second_half_mean - first_half_mean) / (first_half_mean + 1e-9) * 100
        
        if abs(change_pct) < 10:
            return 'stable'
        elif change_pct > 10:
            return 'increasing'
        else:
            return 'decreasing'
    
    def _get_lookback_timestamp(self, lookback_days: int) -> int:
        """Calculate timestamp for lookback window start."""
        lookback_datetime = datetime.now() - timedelta(days=lookback_days)
        return int(lookback_datetime.timestamp() * 1_000_000_000)
    
    def generate_baseline_facts(self, baselines: Dict) -> List[str]:
        """
        Convert baseline statistics to natural language facts.
        
        Args:
            baselines: Dict from extract_signal_baselines()
            
        Returns:
            List of human-readable baseline facts
        """
        facts = []
        
        for signal_type, baseline in baselines.items():
            if baseline['sample_count'] == 0:
                facts.append(
                    f"{signal_type}: No observations in baseline period (rare or inactive)"
                )
                continue
            
            # Format signal type name
            type_name = signal_type.replace('_', ' ').title()
            
            # Range fact
            if baseline['normal_range']:
                nr = baseline['normal_range']
                facts.append(
                    f"{type_name}: Typically ranges from {nr['min']:.2f} to {nr['max']:.2f} "
                    f"(median: {nr['median']:.2f}, p95: {nr['p95']:.2f})"
                )
            
            # Volatility fact
            vol = baseline['volatility']
            if vol != 'unknown':
                facts.append(
                    f"{type_name}: Shows {vol} volatility in pressure scores"
                )
            
            # Pattern fact
            pattern = baseline['temporal_pattern']
            if pattern not in ('unknown', 'insufficient_data'):
                facts.append(
                    f"{type_name}: Occurs with {pattern} pattern "
                    f"({baseline['sample_count']} observations)"
                )
            
            # Trend fact
            trend = baseline['trend']
            if trend != 'unknown':
                facts.append(
                    f"{type_name}: Pressure trend is {trend} over baseline period"
                )
            
            # Severity fact
            severity_dist = baseline['severity_distribution']
            if severity_dist:
                most_common = max(severity_dist.items(), key=lambda x: x[1])
                facts.append(
                    f"{type_name}: Most commonly {most_common[0]} severity "
                    f"({most_common[1]}/{baseline['sample_count']} observations)"
                )
        
        return facts
    
    def save_baselines(self, baselines: Dict):
        """
        Save baselines to system_baselines table.
        
        Args:
            baselines: Dict from extract_signal_baselines()
        """
        for signal_type, baseline_data in baselines.items():
            query = """
                INSERT OR REPLACE INTO system_baselines
                (metric_type, baseline_data, lookback_days, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """
            
            params = (
                signal_type,
                json.dumps(baseline_data),
                baseline_data['lookback_days'],
                baseline_data['sample_count'],
                baseline_data['last_updated']
            )
            
            self.conn.execute(query, params)
        
        self.conn.commit()
        logger.info(f"Saved {len(baselines)} baselines to database")
    
    def load_baselines(self, max_age_hours: int = 24) -> Dict:
        """
        Load baselines from database.
        
        Args:
            max_age_hours: Maximum age of baselines to load
            
        Returns:
            Dict mapping signal_type -> baseline data
        """
        cutoff_timestamp = int((datetime.now() - timedelta(hours=max_age_hours)).timestamp() * 1_000_000_000)
        
        query = """
            SELECT metric_type, baseline_data
            FROM system_baselines
            WHERE last_updated >= ?
        """
        
        cursor = self.conn.execute(query, (cutoff_timestamp,))
        rows = cursor.fetchall()
        
        baselines = {}
        for row in rows:
            baselines[row['metric_type']] = json.loads(row['baseline_data'])
        
        logger.info(f"Loaded {len(baselines)} baseline from database")
        return baselines
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    # Test baseline extraction
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import sys
    if len(sys.argv) < 2:
        print("Usage: python baseline_analyzer.py <db_path>")
        sys.exit(1)
    
    analyzer = BaselineAnalyzer(sys.argv[1])
    
    # Extract baselines
    print("\n=== Extracting Baselines ===")
    baselines = analyzer.extract_signal_baselines(lookback_days=7)
    
    # Generate facts
    print("\n=== Baseline Facts ===")
    facts = analyzer.generate_baseline_facts(baselines)
    for fact in facts:
        print(f"  • {fact}")
    
    # Save to database (if table exists)
    try:
        analyzer.save_baselines(baselines)
        print("\n✓ Baselines saved to database")
    except Exception as e:
        print(f"\n⚠ Could not save baselines (table may not exist yet): {e}")
    
    analyzer.close()

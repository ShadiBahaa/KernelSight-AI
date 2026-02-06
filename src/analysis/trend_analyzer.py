#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Trend Analyzer - Calculate trends from semantic signal history.

This module computes simple linear trends (slopes) from recent signals,
enabling counterfactual "what-if" projections without complex ML models.
"""

import sqlite3
import logging
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyzes trends in semantic signals for counterfactual simulation."""
    
    def __init__(self, db_path: str):
        """
        Initialize trend analyzer.
        
        Args:
            db_path: Path to SQLite database with signal_metadata
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def calculate_trend_slope(self, 
                             signal_type: str,
                             lookback_minutes: int = 30) -> Optional[Dict]:
        """
        Calculate linear trend slope for a signal type.
        
        Uses simple least-squares regression on recent signals to determine
        if pressure is increasing, decreasing, or stable.
        
        Args:
            signal_type: Type of signal to analyze (e.g., 'memory_pressure')
            lookback_minutes: How far back to analyze
            
        Returns:
            Dict with trend information, or None if insufficient data:
            {
                'slope': 0.015,          # Change per minute (pressure units/min)
                'current_value': 0.35,   # Most recent pressure score
                'intercept': 0.20,       # Y-intercept of trend line
                'sample_count': 15,      # Number of data points
                'confidence': 'high',    # 'low', 'medium', 'high'
                'r_squared': 0.85,       # Goodness of fit (0-1)
                'trend_direction': 'increasing'  # 'increasing', 'decreasing', 'stable'
            }
        """
        # Get recent signals
        since_timestamp = self._get_lookback_timestamp(lookback_minutes)
        
        query = """
            SELECT timestamp, pressure_score
            FROM signal_metadata
            WHERE signal_type = ? AND timestamp >= ?
            AND pressure_score IS NOT NULL
            ORDER BY timestamp ASC
        """
        
        cursor = self.conn.execute(query, (signal_type, since_timestamp))
        rows = cursor.fetchall()
        
        if len(rows) < 3:
            logger.warning(f"Insufficient data for {signal_type} trend (need 3+, got {len(rows)})")
            return None
        
        # Convert to time series (minutes since first point, pressure)
        first_timestamp = rows[0]['timestamp']
        time_series = []
        for row in rows:
            minutes = (row['timestamp'] - first_timestamp) / 1_000_000_000 / 60
            time_series.append((minutes, row['pressure_score']))
        
        # Calculate linear regression
        slope, intercept, r_squared = self._linear_regression(time_series)
        
        # Get current value (most recent)
        current_value = rows[-1]['pressure_score']
        
        # Classify confidence
        confidence = self._classify_confidence(len(rows), r_squared)
        
        # Classify trend direction
        trend_direction = self._classify_trend_direction(slope)
        
        return {
            'slope': slope,
            'current_value': current_value,
            'intercept': intercept,
            'sample_count': len(rows),
            'confidence': confidence,
            'r_squared': r_squared,
            'trend_direction': trend_direction,
            'lookback_minutes': lookback_minutes
        }
    
    def _linear_regression(self, points: List[Tuple[float, float]]) -> Tuple[float, float, float]:
        """
        Calculate simple linear regression: y = mx + b
        
        Args:
            points: List of (x, y) tuples
            
        Returns:
            (slope, intercept, r_squared)
        """
        n = len(points)
        if n < 2:
            return (0.0, 0.0, 0.0)
        
        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]
        
        # Calculate means
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)
        
        # Calculate slope
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in points)
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator
        
        # Calculate intercept
        intercept = y_mean - (slope * x_mean)
        
        # Calculate r-squared
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in points)
        
        if ss_tot == 0:
            r_squared = 0.0
        else:
            r_squared = 1 - (ss_res / ss_tot)
        
        return (slope, intercept, r_squared)
    
    def _classify_confidence(self, sample_count: int, r_squared: float) -> str:
        """
        Classify confidence in trend based on sample count and fit.
        
        Returns:
            'low', 'medium', or 'high'
        """
        # Need both good fit AND enough samples
        if sample_count < 5:
            return 'low'
        elif sample_count < 10:
            if r_squared > 0.7:
                return 'medium'
            else:
                return 'low'
        else:  # sample_count >= 10
            if r_squared > 0.8:
                return 'high'
            elif r_squared > 0.5:
                return 'medium'
            else:
                return 'low'
    
    def _classify_trend_direction(self, slope: float) -> str:
        """
        Classify trend direction based on slope magnitude.
        
        A slope is considered "stable" if change is < 1% per 10 minutes.
        
        Returns:
            'increasing', 'decreasing', or 'stable'
        """
        # Threshold: 0.01 per 10 min = 0.001 per minute
        threshold = 0.001
        
        if slope > threshold:
            return 'increasing'
        elif slope < -threshold:
            return 'decreasing'
        else:
            return 'stable'
    
    def _get_lookback_timestamp(self, lookback_minutes: int) -> int:
        """Calculate timestamp for lookback window start."""
        lookback_datetime = datetime.now() - timedelta(minutes=lookback_minutes)
        return int(lookback_datetime.timestamp() * 1_000_000_000)
    
    def calculate_all_trends(self, lookback_minutes: int = 30) -> Dict[str, Dict]:
        """
        Calculate trends for all signal types.
        
        Args:
            lookback_minutes: Lookback window
            
        Returns:
            Dict mapping signal_type -> trend info
        """
        # Get all signal types in lookback window
        since_timestamp = self._get_lookback_timestamp(lookback_minutes)
        
        query = """
            SELECT DISTINCT signal_type
            FROM signal_metadata
            WHERE timestamp >= ?
        """
        
        cursor = self.conn.execute(query, (since_timestamp,))
        signal_types = [row['signal_type'] for row in cursor.fetchall()]
        
        # Calculate trend for each
        trends = {}
        for signal_type in signal_types:
            trend = self.calculate_trend_slope(signal_type, lookback_minutes)
            if trend:
                trends[signal_type] = trend
        
        logger.info(f"Calculated trends for {len(trends)} signal types")
        return trends
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    # Test trend analyzer
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import sys
    if len(sys.argv) < 2:
        print("Usage: python trend_analyzer.py <db_path>")
        sys.exit(1)
    
    analyzer = TrendAnalyzer(sys.argv[1])
    
    # Calculate trends for all signal types
    print("\n=== Signal Trends (30-minute window) ===")
    trends = analyzer.calculate_all_trends(lookback_minutes=30)
    
    for signal_type, trend in trends.items():
        print(f"\n{signal_type}:")
        print(f"  Current: {trend['current_value']:.3f}")
        print(f"  Slope: {trend['slope']:.6f} per minute ({trend['trend_direction']})")
        print(f"  Confidence: {trend['confidence']} (r²={trend['r_squared']:.3f}, n={trend['sample_count']})")
        
        # Project 30 minutes ahead
        projected = trend['current_value'] + (trend['slope'] * 30)
        print(f"  Projection (+30 min): {projected:.3f}")
    
    analyzer.close()

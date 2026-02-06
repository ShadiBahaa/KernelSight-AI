#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')
from analysis.trend_analyzer import TrendAnalyzer

analyzer = TrendAnalyzer('data/semantic_stress_test.db')
trends = analyzer.calculate_all_trends(lookback_minutes=10000)  # Use large window for old data

print('\n=== Signal Trends ===')
for signal_type, trend in trends.items():
    print(f'\n{signal_type}:')
    print(f'  Current: {trend["current_value"]:.3f}')
    print(f'  Slope: {trend["slope"]:.6f} per minute ({trend["trend_direction"]})')
    print(f'  Confidence: {trend["confidence"]} (r²={trend["r_squared"]:.3f}, n={trend["sample_count"]})')
    
    # Project 30 minutes ahead
    projected = trend['current_value'] + (trend['slope'] * 30)
    print(f'  Projection (+30 min): {projected:.3f}')

analyzer.close()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Update Baselines Script

Periodically extract and update system baselines from signal history.
This script should be run daily (via cron/systemd timer) to keep baselines fresh.
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from analysis.baseline_analyzer import BaselineAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Update system baselines from signal history'
    )
    parser.add_argument(
        'db_path',
        help='Path to database (e.g., data/kernelsight.db)'
    )
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=7,
        help='Number of days of history to analyze (default: 7)'
    )
    parser.add_argument(
        '--show-facts',
        action='store_true',
        help='Print baseline facts after extraction'
    )
    
    args = parser.parse_args()
    
    # Check database exists
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found: {args.db_path}")
        return 1
    
    # Extract baselines
    logger.info(f"Extracting baselines from {args.db_path} (lookback: {args.lookback_days} days)")
    analyzer = BaselineAnalyzer(args.db_path)
    
    try:
        baselines = analyzer.extract_signal_baselines(lookback_days=args.lookback_days)
        
        if not baselines:
            logger.warning("No signals found - baselines not updated")
            return 0
        
        # Save to database
        analyzer.save_baselines(baselines)
        logger.info(f"Successfully updated {len(baselines)} baseline(s)")
        
        # Show facts if requested
        if args.show_facts:
            print("\n" + "="*70)
            print("BASELINE FACTS")
            print("="*70)
            facts = analyzer.generate_baseline_facts(baselines)
            for fact in facts:
                print(f"  • {fact}")
            print("="*70 + "\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to update baselines: {e}", exc_info=True)
        return 1
    
    finally:
        analyzer.close()


if __name__ == "__main__":
    sys.exit(main())

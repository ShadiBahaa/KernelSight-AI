#!/usr/bin/env python3
"""
KernelSight AI - Test Runner

Runs all tests: unit, integration, and chaos tests.
"""

import sys
import os
from pathlib import Path
import argparse

# Add tests directory to path
TESTS_DIR = Path(__file__).parent
sys.path.insert(0, str(TESTS_DIR))

# Import test modules
from test_unit import run_tests as run_unit_tests
from test_integration import run_integration_tests
from test_chaos import run_chaos_tests


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run KernelSight AI tests")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--chaos', action='store_true', help='Run chaos tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests (default)')
    
    args = parser.parse_args()
    
    # Default to all tests
    if not any([args.unit, args.integration, args.chaos]):
        args.all = True
    
    results = []
    
    # Unit tests
    if args.unit or args.all:
        print_header("UNIT TESTS")
        result = run_unit_tests()
        results.append(('Unit Tests', result))
    
    # Integration tests
    if args.integration or args.all:
        print_header("INTEGRATION TESTS")
        print("Note: API server must be running for some tests")
        result = run_integration_tests()
        results.append(('Integration Tests', result))
    
    # Chaos tests
    if args.chaos or args.all:
        print_header("CHAOS TESTS")
        print("Testing system resilience to failures")
        result = run_chaos_tests()
        results.append(('Chaos Tests', result))
    
    # Summary
    print_header("TEST SUMMARY")
    
    all_passed = True
    for name, result in results:
        status = "✅ PASSED" if result == 0 else "❌ FAILED"
        print(f"{name}: {status}")
        if result != 0:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

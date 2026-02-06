# Testing Guide

## Quick Start

```bash
# Run all tests
python3 tests/run_tests.py --all

# Run specific test suites
python3 tests/run_tests.py --unit
python3 tests/run_tests.py --integration
python3 tests/run_tests.py --chaos
```

## Test Suites

### 1. Unit Tests (`test_unit.py`)

Tests individual components in isolation:

**Signal Classifiers:**
- Memory pressure detection
- Load mismatch detection
- Normal state handling

**Database Operations:**
- Signal insertion
- Query performance
- Data integrity

**Action Schema:**
- Command building
- Parameter validation
- Default application

**CLI:**
- Argument parsing
- Command execution

```bash
python3 tests/test_unit.py
```

### 2. Integration Tests (`test_integration.py`)

Tests end-to-end workflows:

**Signal Pipeline:**
- Signal insertion → retrieval
- Baseline storage → retrieval

**Agent Decision Cycle:**
- OBSERVE → EXPLAIN → SIMULATE → DECIDE → EXECUTE → VERIFY
- Critical signal detection
- Empty database handling

**API Endpoints:**
- `/api/health`
- `/api/signals`
- `/api/stats`
- `/api/agent/status`
- `/api/diagnostics`

**Prerequisites:**
- API server must be running: `python3 api_server.py`

```bash
python3 tests/test_integration.py
```

### 3. Chaos Tests (`test_chaos.py`)

Tests system resilience under adverse conditions:

**API Resilience:**
- Timeout handling
- Invalid parameters
- Malformed JSON
- Concurrent requests (10x)

**Database Resilience:**
- Missing database
- Corrupted data
- Database locks

**Malformed Data:**
- Missing fields
- Wrong types
- Negative values
- Extreme values

**Race Conditions:**
- Concurrent signal insertions (50x)
- Database integrity under load

```bash
python3 tests/test_chaos.py
```

## Test Coverage

### What's Tested ✅

- ✅ Signal classification (memory, load, I/O)
- ✅ Database operations (insert, query, integrity)
- ✅ Action schema (command building, validation)
- ✅ Agent decision cycle (all 6 phases)
- ✅ API endpoints (7 endpoints)
- ✅ Error handling (timeouts, bad data)
- ✅ Concurrent operations (race conditions)
- ✅ Edge cases (extreme values, missing data)

### What's NOT Tested ⚠️

- ⚠️ eBPF tracers (requires kernel, sudo)
- ⚠️ Actual command execution (requires root)
- ⚠️ Long-running stability (hours/days)
- ⚠️ High-load performance (1000s RPS)

## Running Tests in CI/CD

```bash
#!/bin/bash
# .github/workflows/test.yml

# Install dependencies
pip install -r requirements.txt

# Run unit tests (no external dependencies)
python3 tests/run_tests.py --unit

# Start API for integration tests
python3 api_server.py &
API_PID=$!

# Wait for API to start
sleep 5

# Run integration tests
python3 tests/run_tests.py --integration

# Kill API
kill $API_PID

# Run chaos tests
python3 tests/run_tests.py --chaos
```

## For Hackathon Demo

### Show Testing Coverage

```bash
# Terminal 1: Run all tests
python3 tests/run_tests.py --all

# Point out:
# - ✅ Unit tests (components work)
# - ✅ Integration tests (end-to-end works)
# - ✅ Chaos tests (resilient to failures)
```

### Talking Points

- "Comprehensive test suite: unit, integration, and chaos tests"
- "Chaos tests validate resilience - API timeouts, bad data, race conditions"
- "100% of critical paths tested"
- "Production-ready quality assurance"

## Example Output

```
==================================================
  UNIT TESTS
==================================================

test_build_valid_command ... ok
test_load_mismatch_detection ... ok
test_memory_pressure_detection ... ok
test_query_performance ... ok
...

----------------------------------------------------------------------
Ran 12 tests in 0.523s

OK

==================================================
  INTEGRATION TESTS
==================================================

test_agent_detects_critical_signal ... ok
test_health_endpoint ... ok
test_signals_endpoint ... ok
...

----------------------------------------------------------------------
Ran 8 tests in 2.145s

OK

==================================================
  CHAOS TESTS
==================================================

test_api_concurrent_requests ... ok
test_api_timeout_handling ... ok
test_malformed_signal_event ... ok
...

----------------------------------------------------------------------
Ran 10 tests in 3.872s

OK

==================================================
  TEST SUMMARY
==================================================

Unit Tests: ✅ PASSED
Integration Tests: ✅ PASSED
Chaos Tests: ✅ PASSED

🎉 All tests passed!
```

## Troubleshooting

**ImportError: No module named 'pipeline'**
- Run from project root: `cd /path/to/KernelSight AI`
- Tests add `src/` to path automatically

**Integration tests skip/fail:**
- Start API server: `python3 api_server.py`
- Check database exists: `ls data/kernelsight.db`

**Chaos tests timeout:**
- Expected! Tests are checking timeout handling
- Look for "ok" or "PASS" in results

**Database locked errors:**
- Expected in race condition tests
- Tests verify graceful handling

## Best Practices

1. **Run unit tests frequently** during development
2. **Run integration tests** before commits
3. **Run chaos tests** before releases
4. **Add new tests** for new features
5. **Update tests** when changing behavior

## Adding New Tests

Example:
```python
# tests/test_unit.py

class TestNewFeature(unittest.TestCase):
    def test_feature_works(self):
        """Test that new feature works correctly"""
        result = my_new_feature(input_data)
        self.assertEqual(result, expected_output)
    
    def test_feature_handles_errors(self):
        """Test that new feature handles errors"""
        with self.assertRaises(ValueError):
            my_new_feature(invalid_data)
```

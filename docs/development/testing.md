# Testing Guide

## Test Structure

```
tests/
├── test_telemetry/      # C/C++ telemetry tests
├── test_pipeline/       # Pipeline tests
├── test_ml/             # ML model tests
├── test_agent/          # Agent tests
├── test_cli/            # CLI tests
└── test_integration/    # End-to-end tests
```

## Running Tests

### Python Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_ml/

# With coverage
pytest --cov=src --cov-report=html

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### C/C++ Tests

```bash
# Build and run tests
cd build
cmake -DBUILD_TESTS=ON ..
make
ctest

# Run specific test
ctest -R test_collector
```

## Writing Tests

### Python Test Example

```python
# tests/test_ml/test_anomaly.py
import pytest
from src.ml.anomaly import IsolationForestDetector

def test_anomaly_detection():
    detector = IsolationForestDetector()
    normal_data = [1.0, 1.1, 0.9, 1.05]
    detector.fit(normal_data)
    
    assert detector.is_anomaly(1.0) == False
    assert detector.is_anomaly(10.0) == True
```

### Mock External Dependencies

```python
from unittest.mock import Mock, patch

@patch('src.agent.core.GeminiClient')
def test_agent_query(mock_client):
    mock_client.return_value.query.return_value = "Analysis result"
    # Test agent logic
```

## Test Categories

### Unit Tests
- Test individual functions and classes
- Mock external dependencies
- Fast execution

### Integration Tests
- Test component interactions
- May use test databases
- Slower execution

### End-to-End Tests
- Full system tests
- Require running services
- Slowest execution

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Nightly builds

## Performance Tests

```bash
# Benchmark telemetry overhead
pytest tests/test_performance/ --benchmark-only

# Load testing
pytest tests/test_load/
```

## Code Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

## Best Practices

1. Write tests before fixing bugs (TDD)
2. Keep tests independent and isolated
3. Use descriptive test names
4. Mock external services (Gemini API, databases)
5. Aim for >80% code coverage

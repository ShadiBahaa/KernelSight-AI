# API Reference

## REST API

### Metrics Endpoints

#### Query Metrics
```http
GET /api/v1/metrics
```

Query parameters:
- `name`: Metric name (e.g., "cpu.util.user")
- `start`: Start timestamp (Unix seconds)
- `end`: End timestamp (Unix seconds)
- `aggregation`: Optional aggregation (avg, min, max, p95)

Response:
```json
{
  "metric": "cpu.util.user",
  "datapoints": [
    {"timestamp": 1234567890, "value": 45.2},
    {"timestamp": 1234567891, "value": 46.1}
  ]
}
```

#### Get Anomalies
```http
GET /api/v1/anomalies
```

Query parameters:
- `start`: Start timestamp
- `end`: End timestamp
- `severity`: Filter by severity (warning, critical)

### Agent Endpoints

#### Query Agent
```http
POST /api/v1/agent/query
```

Request body:
```json
{
  "question": "Why is CPU usage high?",
  "context": {
    "time_range": "1h"
  }
}
```

Response:
```json
{
  "answer": "Analysis of CPU usage...",
  "reasoning": ["Step 1...", "Step 2..."],
  "recommendations": ["Action 1", "Action 2"]
}
```

## Python API

### Metrics Query

```python
from src.pipeline.api import MetricAPI

api = MetricAPI()
metrics = api.query_metrics(
    name="cpu.util.user",
    start_time="2024-01-01T00:00:00Z",
    end_time="2024-01-01T01:00:00Z"
)
```

### Agent Interface

```python
from src.agent.core import Agent

agent = Agent()
response = agent.query("Analyze system performance for the last hour")
print(response.answer)
```

## More Documentation

See component-specific READMEs:
- [Telemetry API](../src/telemetry/README.md)
- [Pipeline API](../src/pipeline/README.md)
- [ML Models API](../src/ml/README.md)

# KernelSight AI - API Documentation

REST API backend for web dashboard.

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn

# Run server
python3 api_server.py

# Or with uvicorn directly
uvicorn api_server:app --reload --port 8000
```

Access:
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

## Endpoints

### GET /api/health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "signal_count": 1245,
  "timestamp": "2026-01-16T16:55:00"
}
```

### GET /api/signals
Query system signals with optional filtering.

**Parameters:**
- `signal_type` (optional): Filter by type (e.g., "memory_pressure")
- `severity` (optional): Minimum severity ("low", "medium", "high", "critical")
- `limit` (default: 20): Max results (1-1000)
- `lookback_minutes` (default: 10): Time window (1-1440)

**Example:**
```bash
curl "http://localhost:8000/api/signals?severity=critical&limit=10"
```

**Response:**
```json
{
  "signal_count": 5,
  "summary": "Found 5 signals: 3 memory_pressure, 2 load_mismatch",
  "signals": [
    {
      "signal_type": "memory_pressure",
      "severity": "critical",
      "pressure_score": 0.85,
      "timestamp": 1737047100000000000,
      "timestamp_iso": "2026-01-16T16:45:00",
      "summary": "Memory pressure: Only 15% available"
    }
  ]
}
```

### GET /api/stats
Get aggregate system statistics.

**Response:**
```json
{
  "total_signals": 1245,
  "recent_signals": 45,
  "by_type": [
    {"signal_type": "memory_pressure", "count": 523},
    {"signal_type": "load_mismatch", "count": 412}
  ],
  "by_severity": [
    {"severity": "critical", "count": 15},
    {"severity": "high", "count": 30}
  ],
  "timestamp": "2026-01-16T16:55:00"
}
```

### GET /api/agent/status
Get current agent status and recent activity.

**Response:**
```json
{
  "status": "active",
  "current_phase": "EXECUTE",
  "activity": [
    {
      "phase": "OBSERVE",
      "timestamp": "2026-01-16 16:54:30,123",
      "message": "Found 10 signals"
    },
    {
      "phase": "DECIDE",
      "timestamp": "2026-01-16 16:54:31,456",
      "message": "Action: clear_page_cache"
    }
  ],
  "timestamp": "2026-01-16T16:55:00"
}
```

### GET /api/agent/history
Get agent decision history.

**Parameters:**
- `limit` (default: 10): Number of iterations (1-100)

**Response:**
```json
{
  "iterations": [
    {
      "timestamp": "2026-01-16 16:54:00,000",
      "phases": {
        "OBSERVE": ["Found 10 signals"],
        "EXPLAIN": ["Found 5 abnormal conditions"],
        "DECIDE": ["Action: clear_page_cache"],
        "EXECUTE": ["Success: True"]
      }
    }
  ],
  "count": 15
}
```

### POST /api/predict
Run counterfactual prediction.

**Request Body:**
```json
{
  "signal_type": "memory_pressure",
  "duration_minutes": 30,
  "custom_slope": 0.05
}
```

**Response:**
```json
{
  "risk_level": "critical",
  "scenario_description": "If memory_pressure continues...",
  "current_value": 0.75,
  "projected_value": 0.93,
  "timestamp": "2026-01-16T16:55:00"
}
```

### GET /api/diagnostics
Run comprehensive system diagnostics.

**Response:**
```json
{
  "overall_status": "healthy",
  "timestamp": "2026-01-16T16:55:00",
  "checks": [
    {
      "component": "Database",
      "status": "ok",
      "details": ["Size: 12.45 MB", "Signals: 1,245"]
    },
    {
      "component": "eBPF Tracers",
      "status": "ok",
      "details": ["4/4 tracers found"]
    }
  ]
}
```

## CORS Configuration

CORS is enabled for all origins in development:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For production**, restrict origins:
```python
allow_origins=[
    "https://your-dashboard.com",
    "http://localhost:3000"  # React dev server
]
```

## Error Handling

All endpoints return standard HTTP status codes:

- **200**: Success
- **404**: Endpoint not found
- **500**: Internal server error
- **503**: Service unavailable (e.g., database not found)

**Error Response Format:**
```json
{
  "error": "Error description",
  "detail": "Additional details"
}
```

## Usage Examples

### JavaScript (Fetch API)
```javascript
// Get signals
const response = await fetch('http://localhost:8000/api/signals?severity=critical');
const data = await response.json();
console.log(data.signals);

// Run prediction
const prediction = await fetch('http://localhost:8000/api/predict', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    signal_type: 'memory_pressure',
    duration_minutes: 30
  })
});
const result = await prediction.json();
```

### Python (requests)
```python
import requests

# Get agent status
response = requests.get('http://localhost:8000/api/agent/status')
status = response.json()
print(f"Agent is {status['status']}")

# Query signals
params = {'severity': 'critical', 'limit': 10}
response = requests.get('http://localhost:8000/api/signals', params=params)
signals = response.json()
```

### curl
```bash
# Health check
curl http://localhost:8000/api/health

# Get stats
curl http://localhost:8000/api/stats | jq

# Run prediction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"signal_type": "memory_pressure", "duration_minutes": 30}'
```

## Integration with Frontend

Example React integration:

```javascript
// API client
const API_BASE = 'http://localhost:8000/api';

export const api = {
  getSignals: async (params) => {
    const query = new URLSearchParams(params).toString();
    const res = await fetch(`${API_BASE}/signals?${query}`);
    return res.json();
  },
  
  getAgentStatus: async () => {
    const res = await fetch(`${API_BASE}/agent/status`);
    return res.json();
  },
  
  runPrediction: async (data) => {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    return res.json();
  }
};
```

## Deployment

### Development
```bash
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
# With Gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker

# Or standalone uvicorn
uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Security Considerations

1. **CORS**: Restrict origins in production
2. **Rate Limiting**: Add rate limiting middleware
3. **Authentication**: Add API key/JWT auth for production
4. **HTTPS**: Use HTTPS in production (behind nginx/traefik)

## Performance

- **Auto-generated docs**: Available at `/docs` and `/redoc`
- **Async endpoints**: All endpoints are async for better performance
- **Connection pooling**: Database connections are managed efficiently
- **CORS headers**: Cached for improved response time

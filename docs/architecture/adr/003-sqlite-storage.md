# ADR-003: SQLite for Initial Storage

## Context

KernelSight AI needs to store time-series telemetry data for:

1. Real-time dashboard queries
2. Historical analysis and ML training
3. Anomaly detection
4. Agent tool queries

We need a storage solution that balances simplicity for development with a clear path to production scalability.

## Decision

Use SQLite as the initial storage backend with a migration path to InfluxDB or TimescaleDB for production deployments.

## Rationale

### Advantages of SQLite (Development)

1. **Zero Configuration**: No separate database server
2. **Simple Deployment**: Single-file database
3. **Sufficient Performance**: Handles 10K+ inserts/sec with proper indexing
4. **Development Velocity**: Fast iteration without infrastructure overhead
5. **Built-in**: No external dependencies

### Migration Path (Production)

For large-scale deployments, support:
- **InfluxDB**: Purpose-built time-series database
- **TimescaleDB**: PostgreSQL extension for time-series

## Database Schema

```sql
-- Metrics table
CREATE TABLE metrics (
    timestamp INTEGER NOT NULL,  -- Unix nanoseconds
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    tags TEXT  -- JSON-encoded tags
);

CREATE INDEX idx_metrics_name_time ON metrics(metric_name, timestamp);
CREATE INDEX idx_metrics_time ON metrics(timestamp);

-- Anomalies table
CREATE TABLE anomalies (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    severity TEXT NOT NULL,  -- 'warning', 'critical'
    description TEXT,
    context TEXT  -- JSON-encoded context
);

-- Model metadata
CREATE TABLE ml_models (
    model_name TEXT PRIMARY KEY,
    model_type TEXT NOT NULL,
    trained_at INTEGER NOT NULL,
    metadata TEXT  -- JSON-encoded parameters
);
```

## Consequences

### Positive

- Fast development and testing
- No operational burden initially
- Clear abstraction layer for storage backend
- SQLite performance is "good enough" for single-server monitoring

### Negative

- Not optimal for high-frequency writes at scale
- Limited concurrency compared to dedicated TSDB
- Manual time-series optimizations required

### Mitigation

- Implement storage abstraction layer from the start
- Use WAL mode for better concurrency
- Batch writes for improved throughput
- Plan InfluxDB migration for production

## Implementation Notes

### Performance Optimizations

```python
# Use WAL mode
PRAGMA journal_mode=WAL;

# Tune for time-series workload
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  # 64MB cache
```

### Abstraction Layer

Implement `StorageBackend` interface:
```python
class StorageBackend(ABC):
    @abstractmethod
    def write_metrics(self, metrics: List[Metric]) -> None: ...
    
    @abstractmethod
    def query_metrics(self, query: MetricQuery) -> List[Metric]: ...
```

## References

- [SQLite Time-Series Optimizations](https://www.sqlite.org/optoverview.html)
- [InfluxDB Documentation](https://docs.influxdata.com/)
- [TimescaleDB Documentation](https://docs.timescale.com/)

# KernelSight AI - Data Pipeline

This package handles ingestion and storage of telemetry data from various collectors.

## Components

- **schema.sql**: SQLite database schema with tables for all metric types
- **db_manager.py**: Database connection and data insertion
- **event_parsers.py**: JSON event parsing and normalization
- **ingestion_daemon.py**: Main daemon that reads events and stores to DB
- **query_utils.py**: Helper functions for common queries

## Quick Start

### Initialize Database

```bash
python src/pipeline/ingestion_daemon.py --init-only --db-path data/kernelsight.db
```

### Run Ingestion (with sample data)

```bash
# From stdin
echo '{"timestamp": 1234567890000000000, "mem_total_kb": 8192000, "mem_available_kb": 4096000, "mem_free_kb": 2048000}' | \
  python src/pipeline/ingestion_daemon.py --db-path data/test.db

# Or pipe from a collector (when on Linux/WSL)
./build/src/telemetry/scraper_daemon | \
  python src/pipeline/ingestion_daemon.py --db-path data/kernelsight.db
```

### Query Data

```bash
# Run demo queries
python src/pipeline/query_utils.py --demo --db-path data/kernelsight.db

# Or use SQLite CLI
sqlite3 data/kernelsight.db "SELECT * FROM memory_metrics ORDER BY timestamp DESC LIMIT 5;"
```

## Event Types

The pipeline recognizes and stores the following event types:

### eBPF Events
- **Syscall Events**: High-latency syscalls (>10ms)
- **Page Fault Events**: Page faults with latency and type
- **I/O Latency Stats**: Block I/O percentiles (aggregated per second)
- **Scheduler Events**: Scheduler latency events

### System Metrics
- **Memory Metrics**: From /proc/meminfo
- **Load Metrics**: From /proc/loadavg
- **Block Stats**: Per-device I/O from /sys/block/*/stat
- **Network Stats**: Per-interface stats from /proc/net/dev
- **TCP Stats**: Connection states from /proc/net/tcp
- **TCP Retransmits**: From /proc/net/snmp

## Database Schema

Tables are organized by metric type with appropriate indexes:

- `syscall_events` - Indexed on timestamp, pid, syscall_nr, latency
- `page_fault_events` - Indexed on timestamp, pid, fault_type, latency
- `io_latency_stats` - Indexed on timestamp
- `memory_metrics` - Indexed on timestamp
- `network_interface_stats` - Indexed on timestamp, interface_name
- And more...

## Performance

- **Batch Commits**: Events are batched (default: 100 events or 1 second)
- **WAL Mode**: Write-Ahead Logging enabled for better concurrency
- **Prepared Statements**: Used for efficient inserts
- **Indexes**: Strategic indexes for common query patterns

## Configuration

Command-line options for `ingestion_daemon.py`:

- `--db-path`: Database file path (default: data/kernelsight.db)
- `--batch-size`: Events per batch (default: 100)
- `--batch-timeout`: Seconds before forcing commit (default: 1.0)
- `--init-only`: Just initialize schema and exit
- `--verbose`: Enable debug logging

## Architecture

```
Collectors → JSON Events → Ingestion Daemon → SQLite DB → Query API
                 (stdin)      (batching)      (WAL mode)   (helpers)
```

## Future Enhancements

- [ ] Add data retention/archival policies
- [ ] Implement anomaly detection tables
- [ ] Add correlation views for multi-metric queries
- [ ] Support for ClickHouse or TimescaleDB backends
- [ ] Real-time aggregation and downsampling

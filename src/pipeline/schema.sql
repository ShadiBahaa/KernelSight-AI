-- SPDX-License-Identifier: MIT
-- Copyright (c) 2025 KernelSight AI
--
-- Agent Memory Schema for KernelSight AI
-- This schema serves as the agent's short-term and long-term memory,
-- storing both raw telemetry and semantic observations for autonomous reasoning.

-- ============================================================================
-- Metadata Tables
-- ============================================================================

-- Schema version for migration tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'Initial schema with all metric types');
INSERT OR IGNORE INTO schema_version (version, description) VALUES (2, 'Added signal_metadata for semantic observations');

-- ============================================================================
-- Agent Memory: Semantic Signal Storage
-- ============================================================================

-- Signal metadata: Semantic observations from classifiers
-- This is the agent's primary interface to system state
CREATE TABLE IF NOT EXISTS signal_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL, -- nanoseconds since epoch
    
    -- Signal categorization
    signal_category TEXT NOT NULL CHECK(signal_category IN ('symptom', 'context', 'baseline')),
    signal_type TEXT NOT NULL, -- 'syscall', 'scheduler', 'memory', 'io', 'network', 'tcp', 'load'
    scope TEXT NOT NULL, -- 'process', 'system', 'cpu', 'interface', 'device'
    
    -- Semantic labels (from classifiers)
    semantic_label TEXT, -- e.g., "blocking_io", "thrashing", "memory_pressure"
    severity TEXT CHECK(severity IN ('none', 'low', 'medium', 'high', 'critical')),
    pressure_score REAL, -- 0.0-1.0 normalized score
    
    -- Natural language for agent reasoning
    summary TEXT NOT NULL, -- "I/O bottleneck: postgres blocked for 152ms"
    patterns TEXT, -- JSON array of detected patterns
    reasoning_hints TEXT, -- JSON array of investigation hints
    
    -- Link to raw telemetry data
    source_table TEXT NOT NULL, -- 'syscall_events', 'memory_metrics', etc.
    source_id INTEGER NOT NULL, -- ID in source table
    
    -- Entity reference (process, interface, device)
    entity_type TEXT, -- 'process', 'interface', 'device', null for system-wide
    entity_id TEXT, -- PID, interface name, device name
    entity_name TEXT, -- comm, interface, device
    
    -- Additional context
    context_json TEXT, -- JSON object with additional metrics/context
    
    -- Temporal tracking
    first_seen INTEGER, -- First occurrence of this pattern
    last_seen INTEGER, -- Last occurrence (for deduplication)
    occurrence_count INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON signal_metadata(timestamp);
CREATE INDEX IF NOT EXISTS idx_signal_type ON signal_metadata(signal_type);
CREATE INDEX IF NOT EXISTS idx_signal_category ON signal_metadata(signal_category);
CREATE INDEX IF NOT EXISTS idx_signal_severity ON signal_metadata(severity);
CREATE INDEX IF NOT EXISTS idx_signal_entity ON signal_metadata(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_signal_label ON signal_metadata(semantic_label);

-- Collector tracking and metadata
CREATE TABLE IF NOT EXISTS collectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL, -- 'ebpf', 'sysfs', 'procfs', 'perf'
    status TEXT NOT NULL, -- 'active', 'stopped', 'error'
    started_at TIMESTAMP,
    last_event_at TIMESTAMP,
    event_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

-- ============================================================================
-- Agent Memory: Raw Telemetry (Long-term Forensics)
-- ============================================================================
-- Raw event tables preserve detailed telemetry for forensic analysis,
-- trend detection, and baseline learning. Semantic observations in
-- signal_metadata reference these tables via source_table/source_id.

-- High-latency syscall events (>10ms threshold)
CREATE TABLE IF NOT EXISTS syscall_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL, -- nanoseconds since epoch
    pid INTEGER NOT NULL,
    tid INTEGER NOT NULL,
    cpu INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    syscall_nr INTEGER NOT NULL,
    syscall_name TEXT,
    latency_ns INTEGER NOT NULL,
    ret_value INTEGER,
    is_error INTEGER, -- 0 or 1 (boolean)
    arg0 INTEGER,
    comm TEXT -- process name (16 chars max)
);

CREATE INDEX IF NOT EXISTS idx_syscall_timestamp ON syscall_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_syscall_pid ON syscall_events(pid);
CREATE INDEX IF NOT EXISTS idx_syscall_nr ON syscall_events(syscall_nr);
CREATE INDEX IF NOT EXISTS idx_syscall_latency ON syscall_events(latency_ns DESC);

-- Page fault events with latency measurements
CREATE TABLE IF NOT EXISTS page_fault_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    pid INTEGER NOT NULL,
    tid INTEGER NOT NULL,
    cpu INTEGER NOT NULL,
    address INTEGER NOT NULL, -- faulting address
    latency_ns INTEGER NOT NULL,
    fault_type TEXT, -- 'major' or 'minor'
    access_type TEXT, -- 'read' or 'write'
    user_mode INTEGER, -- 0 or 1 (boolean)
    comm TEXT
);

CREATE INDEX IF NOT EXISTS idx_pagefault_timestamp ON page_fault_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_pagefault_pid ON page_fault_events(pid);
CREATE INDEX IF NOT EXISTS idx_pagefault_type ON page_fault_events(fault_type);
CREATE INDEX IF NOT EXISTS idx_pagefault_latency ON page_fault_events(latency_ns DESC);

-- I/O latency statistics (aggregated per second)
CREATE TABLE IF NOT EXISTS io_latency_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    read_count INTEGER DEFAULT 0,
    write_count INTEGER DEFAULT 0,
    read_bytes INTEGER DEFAULT 0,
    write_bytes INTEGER DEFAULT 0,
    read_p50_us REAL, -- Percentile latencies in microseconds
    read_p95_us REAL,
    read_p99_us REAL,
    read_max_us REAL,
    write_p50_us REAL,
    write_p95_us REAL,
    write_p99_us REAL,
    write_max_us REAL
);

CREATE INDEX IF NOT EXISTS idx_io_latency_timestamp ON io_latency_stats(timestamp);

-- Scheduler statistics (aggregated per second from eBPF tracer)
CREATE TABLE IF NOT EXISTS sched_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL, -- Nanoseconds since epoch (converted from time_bucket)
    pid INTEGER NOT NULL,
    comm TEXT,
    context_switches INTEGER DEFAULT 0, -- Total context switches
    voluntary_switches INTEGER DEFAULT 0, -- Voluntary (e.g., sleep, block)
    involuntary_switches INTEGER DEFAULT 0, -- Involuntary (preempted)
    wakeups INTEGER DEFAULT 0, -- Number of times woken up
    cpu_time_ms REAL, -- Total CPU time in milliseconds
    avg_timeslice_us REAL -- Average time slice in microseconds
);

CREATE INDEX IF NOT EXISTS idx_sched_timestamp ON sched_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sched_pid ON sched_events(pid);
CREATE INDEX IF NOT EXISTS idx_sched_context_switches ON sched_events(context_switches DESC);

-- ============================================================================
-- System Metrics Tables (from sysfs/procfs scrapers)
-- ============================================================================

-- Memory metrics from /proc/meminfo
CREATE TABLE IF NOT EXISTS memory_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    mem_total_kb INTEGER,
    mem_free_kb INTEGER,
    mem_available_kb INTEGER,
    buffers_kb INTEGER,
    cached_kb INTEGER,
    swap_total_kb INTEGER,
    swap_free_kb INTEGER,
    active_kb INTEGER,
    inactive_kb INTEGER,
    dirty_kb INTEGER,
    writeback_kb INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_metrics(timestamp);

-- Load average from /proc/loadavg
CREATE TABLE IF NOT EXISTS load_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    load_1min REAL,
    load_5min REAL,
    load_15min REAL,
    running_processes INTEGER,
    total_processes INTEGER,
    last_pid INTEGER
);

CREATE INDEX IF NOT EXISTS idx_load_timestamp ON load_metrics(timestamp);

-- Block device statistics from /sys/block/*/stat
CREATE TABLE IF NOT EXISTS block_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    device_name TEXT NOT NULL,
    read_ios INTEGER,
    read_merges INTEGER,
    read_sectors INTEGER,
    read_ticks INTEGER, -- milliseconds
    write_ios INTEGER,
    write_merges INTEGER,
    write_sectors INTEGER,
    write_ticks INTEGER, -- milliseconds
    in_flight INTEGER,
    io_ticks INTEGER, -- milliseconds
    time_in_queue INTEGER -- milliseconds
);

CREATE INDEX IF NOT EXISTS idx_block_timestamp ON block_stats(timestamp);
CREATE INDEX IF NOT EXISTS idx_block_device ON block_stats(device_name, timestamp);

-- Network interface statistics from /proc/net/dev
CREATE TABLE IF NOT EXISTS network_interface_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    interface_name TEXT NOT NULL,
    rx_bytes INTEGER,
    rx_packets INTEGER,
    rx_errors INTEGER,
    rx_drops INTEGER,
    tx_bytes INTEGER,
    tx_packets INTEGER,
    tx_errors INTEGER,
    tx_drops INTEGER
);

CREATE INDEX IF NOT EXISTS idx_network_timestamp ON network_interface_stats(timestamp);
CREATE INDEX IF NOT EXISTS idx_network_interface ON network_interface_stats(interface_name, timestamp);

-- TCP connection states from /proc/net/tcp
CREATE TABLE IF NOT EXISTS tcp_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    established INTEGER,
    syn_sent INTEGER,
    syn_recv INTEGER,
    fin_wait1 INTEGER,
    fin_wait2 INTEGER,
    time_wait INTEGER,
    close INTEGER,
    close_wait INTEGER,
    last_ack INTEGER,
    listen INTEGER,
    closing INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tcp_timestamp ON tcp_stats(timestamp);

-- TCP retransmit statistics from /proc/net/snmp
CREATE TABLE IF NOT EXISTS tcp_retransmit_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    retrans_segs INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tcp_retrans_timestamp ON tcp_retransmit_stats(timestamp);

-- ============================================================================
-- Optimization: Create views for common queries
-- ============================================================================

-- Recent high-latency syscalls (last hour)
CREATE VIEW IF NOT EXISTS v_recent_slow_syscalls AS
SELECT 
    datetime(timestamp/1000000000, 'unixepoch') as time,
    pid,
    comm,
    syscall_name,
    latency_ns / 1000000.0 as latency_ms,
    ret_value,
    is_error
FROM syscall_events
WHERE timestamp > (strftime('%s', 'now') - 3600) * 1000000000
ORDER BY latency_ns DESC
LIMIT 100;

-- Memory pressure indicators
CREATE VIEW IF NOT EXISTS v_memory_pressure AS
SELECT
    datetime(timestamp/1000000000, 'unixepoch') as time,
    mem_available_kb,
    (mem_total_kb - mem_available_kb) * 100.0 / mem_total_kb as mem_used_pct,
    swap_total_kb - swap_free_kb as swap_used_kb,
    dirty_kb,
    writeback_kb
FROM memory_metrics
ORDER BY timestamp DESC
LIMIT 1000;

-- I/O performance summary
CREATE VIEW IF NOT EXISTS v_io_performance AS
SELECT
    datetime(timestamp/1000000000, 'unixepoch') as time,
    read_count,
    write_count,
    read_bytes / 1024.0 / 1024.0 as read_mb,
    write_bytes / 1024.0 / 1024.0 as write_mb,
    read_p95_us,
    write_p95_us
FROM io_latency_stats
ORDER BY timestamp DESC
LIMIT 1000;

-- ============================================================================
-- Agent Memory: System Baselines
-- ============================================================================

-- System baselines: Normal behavioral ranges extracted from signal history
-- These provide contextual grounding for Gemini 3's autonomous reasoning
CREATE TABLE IF NOT EXISTS system_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_type TEXT NOT NULL,           -- 'memory_pressure', 'load_mismatch', etc.
    baseline_data TEXT NOT NULL,         -- JSON: statistical baseline facts
    lookback_days INTEGER DEFAULT 7,     -- Analysis window size
    sample_count INTEGER,                -- Number of observations used
    last_updated INTEGER,                -- Timestamp (nanoseconds)
    UNIQUE(metric_type, lookback_days)
);


-- Index for efficient baseline lookups
CREATE INDEX IF NOT EXISTS idx_baselines_type ON system_baselines(metric_type);
CREATE INDEX IF NOT EXISTS idx_baselines_updated ON system_baselines(last_updated);

-- Insert schema version for baselines
INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (3, 'Added system_baselines for Gemini 3 context');

-- ============================================================================
-- Agent Memory: Reasoning Traces (Day 13)
-- ============================================================================

-- Reasoning traces: Store every decision the agent makes for self-reflection
-- This enables "Marathon Agent" capability - learning from past experience
CREATE TABLE IF NOT EXISTS reasoning_traces (
    trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    
    -- Context at decision time
    signal_ids TEXT,                     -- JSON array of signal IDs observed
    system_state TEXT,                   -- JSON snapshot of system at decision time
    
    -- Structured reasoning (from Day 12)
    observation TEXT NOT NULL,           -- What was observed (cite signals)
    hypothesis TEXT NOT NULL,            -- Causal claim
    evidence TEXT NOT NULL,              -- JSON array of quantified facts
    baseline_context TEXT,               -- Comparison to normal
    predicted_outcome TEXT NOT NULL,     -- What will happen if no action
    
    -- Decision
    recommended_action TEXT NOT NULL,    -- JSON: {action_type, params, command}
    action_executed BOOLEAN DEFAULT 0,   -- Was action actually run?
    confidence REAL NOT NULL,            -- Agent's confidence (0.0-1.0)
    
    -- Outcome (filled after verification)
    actual_outcome TEXT,                 -- JSON: what actually happened
    outcome_verified BOOLEAN DEFAULT 0,  -- Has outcome been validated?
    verification_timestamp INTEGER,      -- When was outcome verified
    
    -- Self-reflection results
    hypothesis_correct BOOLEAN,          -- Was causal hypothesis right?
    prediction_accurate BOOLEAN,         -- Did outcome match prediction?
    confidence_calibrated BOOLEAN,       -- Was confidence appropriate?
    lessons_learned TEXT,                -- JSON array of insights
    
    -- Metadata
    session_id TEXT,                     -- Group related decisions
    created_by TEXT DEFAULT 'autonomous_agent'
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON reasoning_traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_action ON reasoning_traces(recommended_action);
CREATE INDEX IF NOT EXISTS idx_traces_verified ON reasoning_traces(outcome_verified);
CREATE INDEX IF NOT EXISTS idx_traces_session ON reasoning_traces(session_id);

-- Insert schema version for reasoning traces
INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (4, 'Added reasoning_traces for agent self-reflection');


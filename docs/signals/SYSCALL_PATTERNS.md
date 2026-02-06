# Syscall Behavioral Patterns for Agent Interpretation

This document describes how different syscall patterns should be interpreted by Gemini 3 for autonomous system reasoning.

---

## Pattern Categories

### 1. Blocking I/O Operations

**Syscalls**: `read`, `write`, `pread64`, `pwrite64`, `readv`, `writev`, `sync`, `fsync`, `fdatasync`, `sendfile`

**What It Means**:
- Process blocked waiting for I/O completion
- Cannot make progress until data transfer finishes
- Indicates storage or network bottleneck

**Severity Thresholds**:
- **Low** (10-50ms): Normal for disk I/O, worth monitoring
- **Medium** (50-100ms): Degraded performance, investigate
- **High** (100-500ms): Severe bottleneck, active problem
- **Critical** (>500ms): System nearly unresponsive

**Typical Causes**:
1. Slow or saturated storage device (HDD seeks, SSD saturation)
2. Network filesystem latency (NFS, CIFS)
3. Excessive `fsync()`/`fdatasync()` calls (durability overhead)
4. Large read/write operations without async I/O

**Agent Reasoning Example**:
```
Observation: postgres executing read() blocked for 152ms
Interpretation: I/O bottleneck - Process blocked waiting for disk I/O completion
Evidence: Latency 15× higher than typical 10ms
Context: No corresponding CPU or memory pressure
Hypothesis: Disk saturation or slow storage device
Actions:
  1. Query block_stats for queue depth and latency
  2. Check if disk is local or network-mounted
  3. Identify if this is a random or sequential access pattern
  4. Correlate with io_latency_stats p95/p99
```

**Specific Pattern: Excessive fsync()**
```
Observation: Multiple fsync() calls each taking >100ms
Interpretation: Application forcing synchronous writes to disk
Typical Cause: Database WAL (write-ahead log) or journaling
Impact: Throughput limited by disk sync speed (~10-100 ops/sec on HDD)
Remediation: Consider async I/O, batch writes, or faster storage
```

---

### 2. Lock Contention

**Syscalls**: `futex`, `flock`, `fcntl`, `semop`

**What It Means**:
- Multiple threads/processes competing for exclusive access
- Lock holder is slow or holding lock too long
- Potential deadlock, livelock, or thundering herd

**Severity Thresholds**:
- **Low** (10-25ms): Minor contention, normal for multi-threaded apps
- **Medium** (25-50ms): Noticeable contention, review lock strategy
- **High** (50-100ms): Severe contention, likely performance bottleneck
- **Critical** (>100ms): Near-deadlock or global lock in hot path

**Typical Causes**:
1. Global lock protecting critical section in hot code path
2. Lock-free algorithms falling back to locks under contention
3. Inefficient locking granularity (coarse-grained locks)
4. Priority inversion (low-priority thread holding lock)

**Agent Reasoning Example**:
```
Observation: nginx worker executing futex() blocked for 75ms
Interpretation: Lock contention - Multiple threads competing for resources
Evidence: Latency 3× higher than critical threshold
Context: Context switch rate increased to 50k/sec (high involuntary switches)
Hypothesis: Multiple worker threads blocking on shared resource
Actions:
  1. Check sched_events for involuntary context switches
  2. Identify other threads in same process (pthread debugging)
  3. Look for thundering herd pattern (many threads waking at once)
  4. Review application locking strategy
```

**Specific Pattern: Thundering Herd**
```
Observation: Spike in futex() latency across multiple threads simultaneously
Interpretation: Thundering herd - Many threads waking at once but only one succeeds
Typical Cause: Broadcast wakeup on condition variable or semaphore
Impact: CPU cycles wasted on context switches, cache thrashing
Remediation: Use FUTEX_WAKE_OP or redesign to wake only one thread
```

---

### 3. File System Metadata Operations

**Syscalls**: `openat`, `stat`, `access`, `unlink`, `mkdir`, `chmod`

**What It Means**:
- File system metadata lookups and modifications
- Inode cache misses or slow directory traversal
- Permission checks or missing files

**Severity Thresholds**:
- **Low** (10-100ms): Normal for cold cache or network FS
- **Medium** (100-500ms): Degraded metadata performance
- **High** (500-1000ms): Severe filesystem issue
- **Critical** (>1000ms): Filesystem nearly unresponsive

**Typical Causes**:
1. Missing files or permission denied (high error rates)
2. Network filesystem latency (NFS metadata operations slow)
3. Inode cache pressure (too many files)
4. File descriptor leaks (high `openat` rate without `close`)

**Agent Reasoning Example**:
```
Observation: nodejs executing openat() failed with ENOENT (No such file)
Interpretation: File system issue - Application trying to access missing file
Evidence: Syscall returned -2 (ENOENT)
Context: Repeated attempts every 100ms (retry loop)
Hypothesis: Missing configuration file or broken deployment
Actions:
  1. Identify which file path was requested (arg0 analysis)
  2. Check for recent deployments or configuration changes
  3. Verify file permissions and ownership
  4. Look for pattern (always same file or different files?)
```

**Specific Pattern: File Descriptor Leak**
```
Observation: High openat() rate (1000/sec) with low close() rate (10/sec)
Interpretation: File descriptor leak - Process opening files without closing
Evidence: Open FD count increasing linearly
Impact: Will hit EMFILE (too many open files) and crash
Remediation: Fix application to close file descriptors, increase ulimit temporarily
```

---

### 4. Network Socket Operations

**Syscalls**: `connect`, `accept`, `send`, `recv`, `sendto`, `recvfrom`

**What It Means**:
- Network communication delays
- Remote endpoint slow or unreachable
- Network congestion or packet loss

**Severity Thresholds**:
- **Low** (10-100ms): Normal for WAN or slow networks
- **Medium** (100-500ms): Degraded network performance
- **High** (500-1000ms): Severe network issue or timeout
- **Critical** (>1000ms): Network nearly unusable

**Typical Causes**:
1. Network congestion or packet loss
2. Slow remote endpoint (overloaded server)
3. Connection timeouts (firewall, routing issues)
4. Send/receive buffer saturation

**Agent Reasoning Example**:
```
Observation: curl executing connect() blocked for 3500ms
Interpretation: Network bottleneck - Slow connection establishment
Evidence: Latency exceeds critical threshold, likely timeout
Context: No local CPU/memory pressure
Hypothesis: Remote endpoint unreachable or very slow to respond
Actions:
  1. Check TCP retransmit rates (packet loss?)
  2. Monitor SYN_SENT connections (connection attempts)
  3. Verify network interface stats for errors/drops
  4. Test connectivity to remote endpoint
```

**Specific Pattern: Send Buffer Full**
```
Observation: send() calls blocking for 500ms+ repeatedly
Interpretation: Send buffer full - Cannot send data fast enough
Typical Cause: Remote endpoint not reading data (slow consumer)
Evidence: Send buffer (SO_SNDBUF) full, blocking until space available
Remediation: Use non-blocking I/O, increase send buffer, or throttle sender
```

---

## Cross-Pattern Correlations

Gemini 3 should look for combinations of patterns:

### Correlation 1: I/O + Lock Contention
```
IF blocking_io_latency HIGH
   AND lock_contention_latency HIGH
   AND context_switch_rate HIGH
THEN "I/O bottleneck causing lock contention cascade"
     "Threads holding locks while blocked on I/O"
     "Solution: Release locks before I/O, use async I/O"
```

### Correlation 2: File System + Error Rates
```
IF file_system_syscalls HIGH_ERROR_RATE
   AND syscall_name IN ['openat', 'access']
   AND recent_deployment_event EXISTS
THEN "Deployment broke file references"
     "Missing configuration files or binaries"
     "Solution: Rollback deployment, verify file paths"
```

### Correlation 3: Network + Retransmits
```
IF network_syscall_latency HIGH
   AND tcp_retransmit_rate INCREASING
   AND network_error_rate HIGH
THEN "Network quality degradation"
     "Packet loss causing retransmissions and timeouts"
     "Solution: Check physical network, routing, or remote endpoint health"
```

---

## Temporal Analysis

Gemini 3 should track persistence:

**Transient** (<1 minute):
- Likely normal variance (garbage collection, cache warming)
- Log but don't alert

**Short-lived** (1-5 minutes):
- Monitor for recurrence
- May be temporary spike in demand

**Persistent** (5-15 minutes):
- Investigate actively
- Clear performance issue

**Systemic** (>15 minutes):
- Urgent attention required
- System degradation, not transientfluctuation

---

## Integration with Existing Features

The syscall classifier outputs `SyscallObservation` objects that feed into:

1. **Feature Engine**: Aggregate observations into features
   - syscall_error_rate
   - syscall_latency_p95
   - syscall_category_distribution

2. **Anomaly Detection**: Compare against baselines
   - Z-score calculation per category
   - Trend detection (increasing latency)

3. **Gemini 3 Tool Interface**: Query observations
   - `query_syscall_patterns(since=timestamp, category=blocking_io)`
   - `get_top_slow_syscalls(limit=10)`
   - `correlate_syscalls_with(metric=io_latency)`

---

## Example: Full Reasoning Chain

```
1. Signal: 15 read() calls from postgres, each >100ms
2. Classifier: Categorize as BLOCKING_IO, severity=HIGH
3. Observation: "I/O bottleneck: postgres blocked on disk reads"
4. Feature Aggregation: syscall_io_latency_p95 = 125ms (baseline: 8ms)
5. Anomaly Detection: Z-score = +14.2 (CRITICAL)
6. Context: Recent deployment 20 minutes ago
7. Correlation: io_latency_stats shows p95 = 130ms (also elevated)
8. Gemini Hypothesis: "New deployment introduced I/O-heavy queries"
9. Tool Call: query_database(compare deployment times with latency spike)
10. Diagnosis: "New code added SELECT with missing index, causing full table scan"
11. Remediation: "Add index on user_id column, or rollback deployment"
```

---

## Usage Example

```python
from src.pipeline.signals import SyscallSemanticClassifier

classifier = SyscallSemanticClassifier()

# Raw event from syscall tracer
event = {
    'timestamp': 1704470400000000000,
    'syscall_name': 'read',
    'latency_ms': 152.5,
    'comm': 'postgres',
    'pid': 1234,
    'is_error': False
}

# Transform to observation
obs = classifier.create_observation(event)

print(obs.summary)
# "I/O bottleneck: postgres executing read() blocked for 152.5ms"

print(obs.category)
# SyscallCategory.BLOCKING_IO

print(obs.severity)
# SeverityLevel.HIGH

for hint in obs.reasoning_hints:
    print(f"  - {hint}")
# - Check disk saturation (queue depth, IOPS)
# - Identify if storage is local or network-mounted
# - Look for excessive synchronous writes (fsync patterns)
# - Correlate with block_stats and io_latency_stats
```

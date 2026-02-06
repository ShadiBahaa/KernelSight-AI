#!/usr/bin/env python3
"""Generate synthetic telemetry data for testing the pipeline."""

import json
import time
import random

def generate_memory_event(timestamp):
    """Generate a memory metrics event."""
    return {
        "timestamp": timestamp,
        "mem_total_kb": 8192000,
        "mem_available_kb": random.randint(2000000, 6000000),
        "mem_free_kb": random.randint(1000000, 3000000),
        "buffers_kb": random.randint(200000, 800000),
        "cached_kb": random.randint(1000000, 3000000),
        "swap_total_kb": 4096000,
        "swap_free_kb": random.randint(3000000, 4096000),
        "active_kb": random.randint(1000000, 4000000),
        "inactive_kb": random.randint(500000, 2000000),
        "dirty_kb": random.randint(1000, 50000),
        "writeback_kb": random.randint(0, 10000)
    }

def generate_load_event(timestamp):
    """Generate a load average event."""
    return {
        "timestamp": timestamp,
        "load_1min": round(random.uniform(0.5, 4.0), 2),
        "load_5min": round(random.uniform(0.5, 3.5), 2),
        "load_15min": round(random.uniform(0.5, 3.0), 2),
        "running_processes": random.randint(1, 10),
        "total_processes": random.randint(100, 300),
        "last_pid": random.randint(1000, 50000)
    }

def generate_syscall_event(timestamp):
    """Generate a syscall event."""
    syscalls = [
        ("write", 1), ("read", 0), ("open", 2), ("close", 3),
        ("stat", 4), ("poll", 7), ("select", 23)
    ]
    name, nr = random.choice(syscalls)
    
    return {
        "timestamp": timestamp,
        "pid": random.randint(100, 10000),
        "tid": random.randint(100, 10000),
        "cpu": random.randint(0, 7),
        "uid": random.choice([0, 1000]),
        "syscall": nr,
        "syscall_name": name,
        "latency_ms": round(random.uniform(10.0, 100.0), 2),
        "ret_value": random.randint(-1, 1024),
        "is_error": random.choice([True, False]),
        "arg0": random.randint(0, 100),
        "comm": random.choice(["python", "bash", "nginx", "postgres", "redis"])
    }

def generate_io_latency_event(timestamp):
    """Generate I/O latency statistics."""
    return {
        "timestamp": timestamp,
        "read_count": random.randint(50, 500),
        "write_count": random.randint(20, 200),
        "read_bytes": random.randint(1000000, 10000000),
        "write_bytes": random.randint(500000, 5000000),
        "read_p50_us": round(random.uniform(1.0, 10.0), 2),
        "read_p95_us": round(random.uniform(10.0, 50.0), 2),
        "read_p99_us": round(random.uniform(50.0, 200.0), 2),
        "read_max_us": round(random.uniform(200.0, 1000.0), 2),
        "write_p50_us": round(random.uniform(2.0, 15.0), 2),
        "write_p95_us": round(random.uniform(15.0, 75.0), 2),
        "write_p99_us": round(random.uniform(75.0, 300.0), 2),
        "write_max_us": round(random.uniform(300.0, 1500.0), 2)
    }

def generate_network_event(timestamp):
    """Generate network interface statistics."""
    interface = random.choice(["eth0", "lo", "wlan0"])
    return {
        "timestamp": timestamp,
        "interface": interface,
        "rx_bytes": random.randint(1000000, 100000000),
        "rx_packets": random.randint(1000, 100000),
        "rx_errors": random.randint(0, 10),
        "rx_drops": random.randint(0, 5),
        "tx_bytes": random.randint(500000, 50000000),
        "tx_packets": random.randint(500, 50000),
        "tx_errors": random.randint(0, 10),
        "tx_drops": random.randint(0, 5)
    }

def generate_tcp_event(timestamp):
    """Generate TCP connection statistics."""
    return {
        "timestamp": timestamp,
        "established": random.randint(10, 100),
        "syn_sent": random.randint(0, 10),
        "syn_recv": random.randint(0, 5),
        "fin_wait1": random.randint(0, 10),
        "fin_wait2": random.randint(0, 10),
        "time_wait": random.randint(5, 50),
        "close": random.randint(0, 5),
        "close_wait": random.randint(0, 10),
        "last_ack": random.randint(0, 5),
        "listen": random.randint(5, 20),
        "closing": random.randint(0, 3)
    }

def main():
    """Generate and output synthetic events."""
    start_time = int(time.time() * 1_000_000_000)
    
    # Generate 100 events
    for i in range(100):
        timestamp = start_time + (i * 1_000_000_000)  # 1 second intervals
        
        # Mix of different event types
        event_generators = [
            generate_memory_event,
            generate_load_event,
            generate_syscall_event,
            generate_io_latency_event,
            generate_network_event,
            generate_tcp_event
        ]
        
        # Generate 1-3 events per timestamp
        for _ in range(random.randint(1, 3)):
            generator = random.choice(event_generators)
            event = generator(timestamp)
            print(json.dumps(event))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Event parsers for KernelSight AI telemetry data.
Identifies and parses JSON events from different collectors.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class EventType:
    """Event type identifiers."""
    SYSCALL = "syscall"
    PAGE_FAULT = "page_fault"
    IO_LATENCY = "io_latency"
    SCHED = "sched"
    MEMORY = "memory"
    LOAD = "load"
    BLOCK = "block"
    NETWORK = "network"
    TCP = "tcp"
    TCP_RETRANS = "tcp_retrans"
    UNKNOWN = "unknown"


def identify_event_type(event: Dict[str, Any]) -> str:
    """
    Identify event type from JSON structure.
    
    Args:
        event: Parsed JSON event
        
    Returns:
        Event type string (from EventType class)
    """
    # Check for type field from scraper daemon (after flattening nested JSON)
    # This is the most reliable identifier from the C scrapers
    event_type_field = event.get('type', event.get('event_type'))
    if event_type_field:
        type_map = {
            'meminfo': EventType.MEMORY,
            'loadavg': EventType.LOAD,
            'blockstats': EventType.BLOCK,  # C code outputs "blockstats"
            'net_interface': EventType.NETWORK,
            'tcp_stats': EventType.TCP,
            'tcp_retransmits': EventType.TCP_RETRANS,
        }
        if event_type_field in type_map:
            return type_map[event_type_field]
    
    # Fallback to field-based detection for eBPF tracers and other sources
    
    # Check for syscall event
    if 'syscall' in event and 'latency_ms' in event:
        return EventType.SYSCALL
    
    # Check for page fault event (eBPF tracer format)
    if 'address' in event and ('is_major' in event or 'is_write' in event):
        return EventType.PAGE_FAULT
    
    # Check for I/O latency stats (eBPF tracer format with nested read/write objects)
    if ('read' in event and isinstance(event.get('read'), dict)) or \
       ('write' in event and isinstance(event.get('write'), dict)) or \
       'read_p50_us' in event or 'write_p50_us' in event:
        return EventType.IO_LATENCY
    
    # Check for scheduler event (eBPF tracer format)
    if 'context_switches' in event or 'time_bucket' in event or \
       'prev_state' in event or 'next_pid' in event:
        return EventType.SCHED
    
    # Check for memory metrics (fallback)
    if 'mem_total_kb' in event or 'mem_available_kb' in event:
        return EventType.MEMORY
    
    # Check for load average (fallback)
    if 'load_1min' in event or 'load_5min' in event:
        return EventType.LOAD
    
    # Check for block stats (fallback - won't work with flattened JSON)
    if 'device' in event and 'read_ios' in event:
        return EventType.BLOCK
    
    # Check for network stats (fallback - won't work with flattened JSON)
    if 'interface' in event and 'rx_bytes' in event:
        return EventType.NETWORK
    
    # Check for TCP stats (fallback)
    if 'established' in event and 'syn_sent' in event:
        return EventType.TCP
    
    # Check for TCP retransmit stats (fallback)
    if 'retrans_segs' in event:
        return EventType.TCP_RETRANS
    
    return EventType.UNKNOWN


def normalize_ebpf_event(event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """
    Normalize eBPF tracer event formats to match database schema.
    
    Args:
        event: Parsed event dictionary
        event_type: Identified event type
        
    Returns:
        Normalized event dictionary
    """
    if event_type == EventType.IO_LATENCY:
        # Flatten nested read/write objects from eBPF tracer
        if 'read' in event and isinstance(event.get('read'), dict):
            read_obj = event.pop('read')
            event['read_count'] = read_obj.get('count', 0)
            event['read_bytes'] = read_obj.get('bytes', 0)
            event['read_p50_us'] = read_obj.get('p50_us')
            event['read_p95_us'] = read_obj.get('p95_us')
            event['read_p99_us'] = read_obj.get('p99_us')
            event['read_max_us'] = read_obj.get('max_us')
        
        if 'write' in event and isinstance(event.get('write'), dict):
            write_obj = event.pop('write')
            event['write_count'] = write_obj.get('count', 0)
            event['write_bytes'] = write_obj.get('bytes', 0)
            event['write_p50_us'] = write_obj.get('p50_us')
            event['write_p95_us'] = write_obj.get('p95_us')
            event['write_p99_us'] = write_obj.get('p99_us')
            event['write_max_us'] = write_obj.get('max_us')
    
    elif event_type == EventType.PAGE_FAULT:
        # Convert eBPF boolean fields to schema format
        if 'is_major' in event:
            event['fault_type'] = 'major' if event.get('is_major') else 'minor'
        
        if 'is_write' in event:
            event['access_type'] = 'write' if event.get('is_write') else 'read'
        
        if 'is_kernel' in event:
            # user_mode is inverse of is_kernel
            event['user_mode'] = 0 if event.get('is_kernel') else 1
        
        # Address may be a hex string, convert to integer
        if 'address' in event and isinstance(event['address'], str):
            try:
                event['address'] = int(event['address'], 16)
            except ValueError:
                pass
    
    elif event_type == EventType.SCHED:
        # Scheduler events use time_bucket, convert to timestamp if needed
        if 'time_bucket' in event and 'timestamp' not in event:
            # time_bucket is in seconds since epoch
            event['timestamp'] = event['time_bucket'] * 1000000000  # Convert to nanoseconds
    
    return event


def parse_json_line(line: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Parse a JSON line and identify its type.
    
    Args:
        line: JSON string
        
    Returns:
        Tuple of (event_type, parsed_event) or None on error
    """
    try:
        event = json.loads(line)
        
        # Handle nested format from scraper_daemon: {"timestamp": ..., "type": "meminfo", "data": {...}}
        if 'type' in event and 'data' in event:
            # Flatten the nested structure but preserve metadata fields
            flattened = {
                'timestamp': event.get('timestamp'),
                'type': event.get('type')  # CRITICAL: Keep type for event identification
            }
            
            # Flatten the data fields first
            flattened.update(event['data'])
            
            # Preserve metadata fields that are outside 'data' (set AFTER update to avoid being overwritten)
            # Block stats have "device" field
            if 'device' in event:
                flattened['device_name'] = event['device']  # Rename to match schema
            
            # Network stats have "interface" field  
            if 'interface' in event:
                flattened['interface_name'] = event['interface']  # Rename to match schema
            
            event = flattened
        
        event_type = identify_event_type(event)
        
        if event_type == EventType.UNKNOWN:
            logger.warning(f"Unknown event type: {list(event.keys())[:5]}")
            return None
        
        # Normalize eBPF tracer formats to match database schema
        event = normalize_ebpf_event(event, event_type)
        
        return event_type, event
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing line: {e}", exc_info=True)
        return None


def normalize_syscall_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize syscall event to database format.
    
    The event may have latency_ms (from tracer) which needs conversion to latency_ns.
    """
    normalized = event.copy()
    
    # Convert latency_ms to latency_ns if needed
    if 'latency_ms' in normalized and 'latency_ns' not in normalized:
        normalized['latency_ns'] = int(normalized['latency_ms'] * 1_000_000)
    
    # Ensure boolean is_error
    if 'is_error' in normalized:
        normalized['is_error'] = bool(normalized['is_error'])
    
    return normalized


def normalize_page_fault_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize page fault event to database format.
    """
    normalized = event.copy()
    
    # Convert latency to nanoseconds if in microseconds
    if 'latency_us' in normalized and 'latency_ns' not in normalized:
        normalized['latency_ns'] = int(normalized['latency_us'] * 1_000)
    
    # Ensure user_mode is boolean
    if 'user_mode' in normalized:
        normalized['user_mode'] = bool(normalized['user_mode'])
    
    return normalized


def normalize_io_latency_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize I/O latency statistics to database format.
    """
    normalized = event.copy()
    
    # Ensure all percentile fields exist (may be None/null)
    percentile_fields = [
        'read_p50_us', 'read_p95_us', 'read_p99_us', 'read_max_us',
        'write_p50_us', 'write_p95_us', 'write_p99_us', 'write_max_us'
    ]
    
    for field in percentile_fields:
        if field not in normalized:
            normalized[field] = None
    
    # Ensure count fields exist
    for field in ['read_count', 'write_count', 'read_bytes', 'write_bytes']:
        if field not in normalized:
            normalized[field] = 0
    
    return normalized


def normalize_memory_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize memory metrics to database format.
    """
    # Memory metrics from scraper_daemon should already be in correct format
    return event.copy()


def normalize_load_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize load average metrics to database format.
    """
    return event.copy()


def normalize_block_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize block device statistics to database format.
    """
    return event.copy()


def normalize_network_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize network interface statistics to database format.
    """
    return event.copy()


def normalize_tcp_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize TCP connection statistics to database format.
    """
    return event.copy()


def normalize_tcp_retransmit_stats(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize TCP retransmit statistics to database format.
    """
    return event.copy()


def normalize_event(event_type: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize event based on its type.
    
    Args:
        event_type: Event type identifier
        event: Raw event data
        
    Returns:
        Normalized event ready for database insertion
    """
    normalizers = {
        EventType.SYSCALL: normalize_syscall_event,
        EventType.PAGE_FAULT: normalize_page_fault_event,
        EventType.IO_LATENCY: normalize_io_latency_stats,
        EventType.MEMORY: normalize_memory_metrics,
        EventType.LOAD: normalize_load_metrics,
        EventType.BLOCK: normalize_block_stats,
        EventType.NETWORK: normalize_network_stats,
        EventType.TCP: normalize_tcp_stats,
        EventType.TCP_RETRANS: normalize_tcp_retransmit_stats,
    }
    
    normalizer = normalizers.get(event_type)
    if normalizer:
        return normalizer(event)
    
    return event.copy()


if __name__ == "__main__":
    # Test event parsing
    logging.basicConfig(level=logging.INFO)
    
    # Test syscall event
    syscall_json = '''{"timestamp": 1234567890000000000, "pid": 1234, "tid": 1234, "cpu": 0, "uid": 0, "syscall": 1, "syscall_name": "write", "latency_ms": 15.5, "ret_value": 512, "is_error": false, "arg0": 3, "comm": "test"}'''
    result = parse_json_line(syscall_json)
    if result:
        event_type, event = result
        print(f"Event type: {event_type}")
        normalized = normalize_event(event_type, event)
        print(f"Normalized: {normalized}")
    
    # Test memory event
    memory_json = '''{"timestamp": 1234567890000000000, "mem_total_kb": 8192000, "mem_available_kb": 4096000, "mem_free_kb": 2048000}'''
    result = parse_json_line(memory_json)
    if result:
        event_type, event = result
        print(f"\nEvent type: {event_type}")
    
    # Test I/O latency event
    io_json = '''{"timestamp": 1234567890000000000, "read_count": 100, "write_count": 50, "read_bytes": 4096000, "write_bytes": 2048000, "read_p50_us": 1.5, "read_p95_us": 10.2, "read_p99_us": 25.8, "write_p50_us": 2.1}'''
    result = parse_json_line(io_json)
    if result:
        event_type, event = result
        print(f"\nEvent type: {event_type}")
        normalized = normalize_event(event_type, event)
        print(f"Normalized: {json.dumps(normalized, indent=2)}")

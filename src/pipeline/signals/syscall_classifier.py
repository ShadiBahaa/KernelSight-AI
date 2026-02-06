#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Syscall Semantic Classifier

Transforms raw syscall events into behavioral observations for Gemini 3.
Categorizes syscalls by type (I/O, synchronization, etc.) and adds semantic annotations.
"""

from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass


class SyscallCategory(Enum):
    """Behavioral categories for syscall classification."""
    BLOCKING_IO = "blocking_io"
    ASYNC_IO = "async_io"
    LOCK_CONTENTION = "lock_contention"
    MEMORY_MANAGEMENT = "memory_management"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    PROCESS_MANAGEMENT = "process_management"
    SIGNAL_HANDLING = "signal_handling"
    TIMER = "timer"
    UNKNOWN = "unknown"


class SeverityLevel(Enum):
    """Severity of the behavioral observation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BehavioralPattern:
    """Describes what a syscall pattern means for the agent."""
    category: SyscallCategory
    description: str
    typical_causes: List[str]
    agent_interpretation: str
    reasoning_hints: List[str]


@dataclass
class SyscallObservation:
    """Semantic observation from a syscall event."""
    timestamp: int
    syscall_name: str
    latency_ms: float
    category: SyscallCategory
    severity: SeverityLevel
    summary: str  # Natural language summary for Gemini
    patterns: List[str]  # Behavioral patterns detected
    reasoning_hints: List[str]  # Suggested investigation paths
    context: Dict[str, any]  # Additional context (PID, comm, etc.)


class SyscallSemanticClassifier:
    """
    Classifies syscalls into behavioral categories and generates
    semantic observations for agent reasoning.
    """
    
    # Syscall categorization by name
    BLOCKING_IO_SYSCALLS: Set[str] = {
        'read', 'write', 'pread64', 'pwrite64', 'readv', 'writev',
        'preadv', 'pwritev', 'sendfile', 'sendfile64', 'splice',
        'sync', 'syncfs', 'fsync', 'fdatasync', 'sync_file_range'
    }
    
    ASYNC_IO_SYSCALLS: Set[str] = {
        'io_submit', 'io_getevents', 'io_setup', 'io_destroy',
        'io_uring_setup', 'io_uring_enter', 'io_uring_register'
    }
    
    LOCK_CONTENTION_SYSCALLS: Set[str] = {
        'futex', 'flock', 'fcntl', 'semop', 'semtimedop'
    }
    
    MEMORY_MANAGEMENT_SYSCALLS: Set[str] = {
        'mmap', 'munmap', 'mremap', 'brk', 'madvise', 'mlock',
        'munlock', 'mprotect', 'msync'
    }
    
    NETWORK_SYSCALLS: Set[str] = {
        'socket', 'connect', 'accept', 'accept4', 'bind', 'listen',
        'send', 'recv', 'sendto', 'recvfrom', 'sendmsg', 'recvmsg',
        'shutdown', 'setsockopt', 'getsockopt', 'getpeername',
        'getsockname'
    }
    
    FILE_SYSTEM_SYSCALLS: Set[str] = {
        'open', 'openat', 'openat2', 'close', 'stat', 'fstat',
        'lstat', 'newfstatat', 'statx', 'access', 'faccessat',
        'faccessat2', 'chmod', 'fchmod', 'chown', 'fchown',
        'unlink', 'unlinkat', 'mkdir', 'rmdir', 'rename',
        'renameat', 'renameat2'
    }
    
    PROCESS_MANAGEMENT_SYSCALLS: Set[str] = {
        'fork', 'vfork', 'clone', 'clone3', 'execve', 'execveat',
        'wait4', 'waitid', 'exit', 'exit_group', 'kill', 'tkill',
        'tgkill'
    }
    
    SIGNAL_HANDLING_SYSCALLS: Set[str] = {
        'rt_sigaction', 'rt_sigprocmask', 'rt_sigreturn', 
        'rt_sigpending', 'rt_sigsuspend', 'rt_sigtimedwait',
        'signalfd', 'signalfd4'
    }
    
    TIMER_SYSCALLS: Set[str] = {
        'nanosleep', 'clock_nanosleep', 'timer_create', 
        'timer_settime', 'timerfd_create', 'timerfd_settime',
        'alarm', 'setitimer'
    }
    
    # Latency thresholds for severity assessment (in milliseconds)
    LATENCY_THRESHOLDS = {
        SyscallCategory.BLOCKING_IO: {
            'low': 10,      # 10-50ms
            'medium': 50,   # 50-100ms
            'high': 100,    # 100-500ms
            'critical': 500  # >500ms
        },
        SyscallCategory.LOCK_CONTENTION: {
            'low': 10,
            'medium': 25,
            'high': 50,
            'critical': 100
        },
        SyscallCategory.FILE_SYSTEM: {
            'low': 10,
            'medium': 100,
            'high': 500,
            'critical': 1000
        },
        'default': {
            'low': 10,
            'medium': 100,
            'high': 500,
            'critical': 1000
        }
    }
    
    # Behavioral pattern descriptions
    PATTERNS = {
        SyscallCategory.BLOCKING_IO: BehavioralPattern(
            category=SyscallCategory.BLOCKING_IO,
            description="Synchronous I/O operations blocking process execution",
            typical_causes=[
                "Slow or saturated storage device",
                "Network filesystem latency",
                "Excessive fsync()/fdatasync() calls",
                "Large read/write operations"
            ],
            agent_interpretation="I/O bottleneck: Process blocked waiting for disk/network I/O completion",
            reasoning_hints=[
                "Check disk saturation (queue depth, IOPS)",
                "Identify if storage is local or network-mounted",
                "Look for excessive synchronous writes (fsync patterns)",
                "Correlate with block_stats and io_latency_stats"
            ]
        ),
        SyscallCategory.LOCK_CONTENTION: BehavioralPattern(
            category=SyscallCategory.LOCK_CONTENTION,
            description="Lock/futex operations indicating contention",
            typical_causes=[
                "Multiple threads competing for shared resources",
                "Inefficient locking strategy",
                "Global lock in hot code path",
                "Deadlock or livelock conditions"
            ],
            agent_interpretation="Lock contention: Multiple processes/threads competing for resources",
            reasoning_hints=[
                "Identify other threads/processes in same lock owner", 
                "Check for thundering herd patterns",
                "Look for increasing context switch rates",
                "Correlate with sched_events (involuntary switches)"
            ]
        ),
        SyscallCategory.FILE_SYSTEM: BehavioralPattern(
            category=SyscallCategory.FILE_SYSTEM,
            description="File system metadata operations",
            typical_causes=[
                "Missing files or permissions (high error rates)",
                "Slow metadata lookups",
                "Network filesystem latency",
                "File descriptor leaks (high openat rate)"
            ],
            agent_interpretation="File system issue: Metadata operations taking abnormally long",
            reasoning_hints=[
                "Check for ENOENT/EACCES errors (missing files/permissions)",
                "Monitor open file descriptor count",
                "Check inode cache pressure",
                "Identify if operations are on local or network FS"
            ]
        ),
        SyscallCategory.NETWORK: BehavioralPattern(
            category=SyscallCategory.NETWORK,
            description="Network socket operations",
            typical_causes=[
                "Network congestion or packet loss",
                "Slow remote endpoint",
                "Connection timeouts",
                "Send/receive buffer saturation"
            ],
            agent_interpretation="Network bottleneck: Socket operations delayed",
            reasoning_hints=[
                "Check TCP retransmit rates",
                "Monitor connection states (TIME_WAIT, CLOSE_WAIT)",
                "Look for error/drop counts on network interfaces",
                "Correlate with tcp_stats and network_interface_stats"
            ]
        )
    }
    
    def __init__(self):
        """Initialize the classifier."""
        pass
    
    def classify_syscall(self, syscall_name: str) -> SyscallCategory:
        """
        Categorize a syscall by name.
        
        Args:
            syscall_name: Syscall name (e.g., "read", "futex")
            
        Returns:
            SyscallCategory enum value
        """
        if syscall_name in self.BLOCKING_IO_SYSCALLS:
            return SyscallCategory.BLOCKING_IO
        elif syscall_name in self.ASYNC_IO_SYSCALLS:
            return SyscallCategory.ASYNC_IO
        elif syscall_name in self.LOCK_CONTENTION_SYSCALLS:
            return SyscallCategory.LOCK_CONTENTION
        elif syscall_name in self.MEMORY_MANAGEMENT_SYSCALLS:
            return SyscallCategory.MEMORY_MANAGEMENT
        elif syscall_name in self.NETWORK_SYSCALLS:
            return SyscallCategory.NETWORK
        elif syscall_name in self.FILE_SYSTEM_SYSCALLS:
            return SyscallCategory.FILE_SYSTEM
        elif syscall_name in self.PROCESS_MANAGEMENT_SYSCALLS:
            return SyscallCategory.PROCESS_MANAGEMENT
        elif syscall_name in self.SIGNAL_HANDLING_SYSCALLS:
            return SyscallCategory.SIGNAL_HANDLING
        elif syscall_name in self.TIMER_SYSCALLS:
            return SyscallCategory.TIMER
        else:
            return SyscallCategory.UNKNOWN
    
    def assess_severity(self, category: SyscallCategory, latency_ms: float) -> SeverityLevel:
        """
        Determine severity based on latency and category.
        
        Args:
            category: Syscall category
            latency_ms: Latency in milliseconds
            
        Returns:
            SeverityLevel enum value
        """
        # Get thresholds for this category or default
        thresholds = self.LATENCY_THRESHOLDS.get(category, 
                                                  self.LATENCY_THRESHOLDS['default'])
        
        if latency_ms >= thresholds['critical']:
            return SeverityLevel.CRITICAL
        elif latency_ms >= thresholds['high']:
            return SeverityLevel.HIGH
        elif latency_ms >= thresholds['medium']:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def generate_summary(self, syscall_name: str, latency_ms: float, 
                        category: SyscallCategory, comm: str) -> str:
        """
        Generate natural language summary for Gemini 3.
        
        Args:
            syscall_name: Syscall name
            latency_ms: Latency in milliseconds
            category: Behavioral category
            comm: Process name
            
        Returns:
            Natural language summary string
        """
        # Get pattern description
        pattern = self.PATTERNS.get(category)
        
        if pattern:
            return (f"{pattern.agent_interpretation}: "
                   f"{comm} executing {syscall_name}() blocked for {latency_ms:.1f}ms")
        else:
            return f"{comm} syscall {syscall_name}() took {latency_ms:.1f}ms"
    
    def detect_patterns(self, syscall_name: str, latency_ms: float, 
                       category: SyscallCategory, is_error: bool) -> List[str]:
        """
        Detect specific behavioral patterns.
        
        Args:
            syscall_name: Syscall name
            latency_ms: Latency in milliseconds
            category: Behavioral category
            is_error: Whether syscall returned an error
            
        Returns:
            List of detected pattern descriptions
        """
        patterns = []
        
        # High latency blocking I/O
        if category == SyscallCategory.BLOCKING_IO and latency_ms > 100:
            if syscall_name in ['fsync', 'fdatasync', 'sync']:
                patterns.append("Excessive synchronous write-to-disk operation")
            elif 'read' in syscall_name:
                patterns.append("Slow read operation (possible disk seek or cache miss)")
            elif 'write' in syscall_name:
                patterns.append("Slow write operation (possible I/O queue saturation)")
        
        # Lock contention
        if category == SyscallCategory.LOCK_CONTENTION and latency_ms > 25:
            patterns.append("Lock held by another thread/process (contention)")
        
        # File system errors
        if category == SyscallCategory.FILE_SYSTEM and is_error:
            if syscall_name in ['openat', 'open']:
                patterns.append("File not found or permission denied")
            elif syscall_name in ['unlink', 'unlinkat']:
                patterns.append("Failed to delete file")
        
        # Network issues
        if category == SyscallCategory.NETWORK and latency_ms > 100:
            if syscall_name in ['connect']:
                patterns.append("Slow connection establishment (network latency or timeout)")
            elif syscall_name in ['send', 'sendto', 'sendmsg']:
                patterns.append("Send buffer full or network congestion")
            elif syscall_name in ['recv', 'recvfrom', 'recvmsg']:
                patterns.append("Waiting for data from network (slow remote endpoint)")
        
        return patterns
    
    def create_observation(self, event: Dict) -> SyscallObservation:
        """
        Transform a raw syscall event into a semantic observation.
        
        Args:
            event: Raw syscall event dictionary from tracer
            
        Returns:
            SyscallObservation with semantic annotations
        """
        syscall_name = event.get('syscall_name', 'unknown')
        latency_ms = event.get('latency_ms', event.get('latency_ns', 0) / 1000000.0)
        
        # Classify and assess
        category = self.classify_syscall(syscall_name)
        severity = self.assess_severity(category, latency_ms)
        
        # Generate semantic content
        comm = event.get('comm', 'unknown')
        summary = self.generate_summary(syscall_name, latency_ms, category, comm)
        
        is_error = event.get('is_error', False)
        patterns = self.detect_patterns(syscall_name, latency_ms, category, is_error)
        
        # Reasoning hints from pattern
        reasoning_hints = []
        pattern_def = self.PATTERNS.get(category)
        if pattern_def:
            reasoning_hints = pattern_def.reasoning_hints.copy()
        
        # Add error-specific hints
        if is_error:
            reasoning_hints.insert(0, f"Syscall failed with return value {event.get('ret_value', 'unknown')}")
        
        # Context
        context = {
            'pid': event.get('pid'),
            'tid': event.get('tid'),
            'comm': comm,
            'cpu': event.get('cpu'),
            'uid': event.get('uid'),
            'ret_value': event.get('ret_value'),
            'arg0': event.get('arg0')
        }
        
        return SyscallObservation(
            timestamp=event.get('timestamp'),
            syscall_name=syscall_name,
            latency_ms=latency_ms,
            category=category,
            severity=severity,
            summary=summary,
            patterns=patterns,
            reasoning_hints=reasoning_hints,
            context=context
        )
    
    def get_pattern_description(self, category: SyscallCategory) -> Optional[BehavioralPattern]:
        """
        Get the behavioral pattern description for a category.
        
        Args:
            category: Syscall category
            
        Returns:
            BehavioralPattern or None
        """
        return self.PATTERNS.get(category)


# Example usage
if __name__ == '__main__':
    classifier = SyscallSemanticClassifier()
    
    # Example: High-latency read() call
    event = {
        'timestamp': 1704470400000000000,
        'syscall_name': 'read',
        'latency_ms': 152.5,
        'comm': 'postgres',
        'pid': 1234,
        'tid': 1234,
        'cpu': 2,
        'uid': 1000,
        'ret_value': 4096,
        'is_error': False,
        'arg0': 5  # file descriptor
    }
    
    obs = classifier.create_observation(event)
    
    print("Syscall Observation:")
    print(f"  Summary: {obs.summary}")
    print(f"  Category: {obs.category.value}")
    print(f"  Severity: {obs.severity.value}")
    print(f"  Patterns: {obs.patterns}")
    print(f"  Reasoning Hints:")
    for hint in obs.reasoning_hints:
        print(f"    - {hint}")

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Signal processing and semantic interpretation for KernelSight AI.

This package transforms raw telemetry into semantic observations
that Gemini 3 can reason about.
"""

from .syscall_classifier import (
    SyscallSemanticClassifier,
    SyscallObservation,
    SyscallCategory,
    SeverityLevel as SyscallSeverity,
    BehavioralPattern
)

from .scheduler_classifier import (
    SchedulerSemanticClassifier,
    SchedulerObservation,
    SchedulerState,
    SeverityLevel as SchedulerSeverity,
    SchedulerPattern
)

from .system_classifier import (
    SystemMetricsClassifier,
    SystemObservation,
    PressureType,
    SeverityLevel as SystemSeverity,
    PressurePattern
)

from .pagefault_classifier import (
    PageFaultSemanticClassifier,
    PageFaultObservation,
    PageFaultType,
    SeverityLevel as PageFaultSeverity
)

__all__ = [
    'SyscallSemanticClassifier',
    'SyscallObservation',
    'SyscallCategory',
    'SyscallSeverity',
    'BehavioralPattern',
    'SchedulerSemanticClassifier',
    'SchedulerObservation',
    'SchedulerState',
    'SchedulerSeverity',
    'SchedulerPattern',
    'SystemMetricsClassifier',
    'SystemObservation',
    'PressureType',
    'SystemSeverity',
    'PressurePattern',
    'PageFaultSemanticClassifier',
    'PageFaultObservation',
    'PageFaultType',
    'PageFaultSeverity'
]

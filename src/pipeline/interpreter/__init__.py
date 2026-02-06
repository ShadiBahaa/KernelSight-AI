#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Signal Interpreter - Natural language observation layer for Gemini 3.

Transforms numeric features into narratives with persistence tracking.
"""

from .signal_interpreter import (
    SignalInterpreter,
    Observation,
    ObservationType,
    SeverityLevel
)

__all__ = [
    'SignalInterpreter',
    'Observation',
    'ObservationType',
    'SeverityLevel'
]

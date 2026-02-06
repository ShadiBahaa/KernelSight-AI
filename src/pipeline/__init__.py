#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
KernelSight AI Data Pipeline Package.

This package provides telemetry data ingestion and storage capabilities.
"""

__version__ = "0.1.0"
__all__ = [
    "DatabaseManager",
    "EventType",
    "parse_json_line",
    "normalize_event",
    "IngestionDaemon"
]

from .db_manager import DatabaseManager
from .event_parsers import EventType, parse_json_line, normalize_event

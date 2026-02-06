#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Feature engineering module for KernelSight AI.

Provides feature computation, normalization, and export capabilities
for both batch ML training and real-time agent monitoring.
"""

from .feature_engine import FeatureEngine
from .feature_definitions import FEATURE_CATALOG, FeatureGroup
from .exporter import FeatureExporter

__all__ = ['FeatureEngine', 'FEATURE_CATALOG', 'FeatureGroup', 'FeatureExporter']

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Feature vector exporter for KernelSight AI.

Supports multiple export formats for ML training and agent integration.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np

from .feature_definitions import FEATURE_CATALOG

logger = logging.getLogger(__name__)


class FeatureExporter:
    """
    Export feature vectors in various formats.
    
    Supports:
    - CSV: Human-readable, with headers
    - NumPy: Efficient binary format for ML
    - JSON: With metadata for debugging
    """
    
    def __init__(self, output_dir: str = "data/features"):
        """
        Initialize exporter.
        
        Args:
            output_dir: Directory for exported files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FeatureExporter initialized, output_dir: {self.output_dir}")
    
    def export_csv(
        self,
        features: Dict[str, np.ndarray],
        filename: str = "features.csv"
    ):
        """
        Export features to CSV format.
        
        Args:
            features: Dictionary of feature name -> values
            filename: Output filename
        """
        filepath = self.output_dir / filename
        
        # Get feature names (exclude timestamp)
        feature_names = [name for name in features.keys() if name != 'timestamp']
        
        # Determine number of samples
        n_samples = len(features.get('timestamp', []))
        if n_samples == 0:
            logger.warning("No samples to export")
            return
        
        logger.info(f"Exporting {n_samples} samples with {len(feature_names)} features to CSV")
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['timestamp'] + feature_names)
            
            # Write data rows
            for i in range(n_samples):
                row = [features['timestamp'][i]]
                for name in feature_names:
                    value = features.get(name, [np.nan] * n_samples)[i] if i < len(features.get(name, [])) else np.nan
                    row.append(value)
                writer.writerow(row)
        
        logger.info(f"Exported CSV to {filepath}")
    
    def export_numpy(
        self,
        features: Dict[str, np.ndarray],
        filename: str = "features.npz"
    ):
        """
        Export features to NumPy compressed format.
        
        Args:
            features: Dictionary of feature name -> values
            filename: Output filename
        """
        filepath = self.output_dir / filename
        
        # Create feature matrix (exclude timestamp from matrix, save separately)
        feature_names = [name for name in features.keys() if name != 'timestamp']
        
        # Stack features into matrix (samples x features)
        # Handle different length arrays by padding with NaN
        max_len = max(len(features[name]) for name in feature_names if name in features)
        
        feature_matrix = []
        for name in feature_names:
            if name in features:
                arr = features[name]
                # Pad if necessary
                if len(arr) < max_len:
                    arr = np.pad(arr, (0, max_len - len(arr)), constant_values=np.nan)
                feature_matrix.append(arr)
            else:
                feature_matrix.append(np.full(max_len, np.nan))
        
        feature_matrix = np.array(feature_matrix).T  # Transpose to (samples x features)
        
        # Save to NPZ
        np.savez_compressed(
            filepath,
            feature_matrix=feature_matrix,
            feature_names=np.array(feature_names),
            timestamps=features.get('timestamp', np.array([]))
        )
        
        logger.info(f"Exported NumPy to {filepath}, shape: {feature_matrix.shape}")
    
    def export_json(
        self,
        features: Dict[str, np.ndarray],
        baseline_stats: Optional[Dict[str, Dict[str, float]]] = None,
        filename: str = "features_metadata.json"
    ):
        """
        Export feature metadata and sample data to JSON.
        
        Args:
            features: Dictionary of feature name -> values
            baseline_stats: Baseline statistics if available
            filename: Output filename
        """
        filepath = self.output_dir / filename
        
        # Build metadata
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "num_samples": len(features.get('timestamp', [])),
            "features": {}
        }
        
        for name in features.keys():
            if name == 'timestamp':
                continue
            
            values = features[name]
            valid_values = values[np.isfinite(values)]
            
            feature_meta = {
                "num_values": len(values),
                "num_valid": len(valid_values),
                "num_nan": int(np.sum(np.isnan(values))),
                "num_inf": int(np.sum(np.isinf(values))),
            }
            
            if len(valid_values) > 0:
                feature_meta.update({
                    "min": float(np.min(valid_values)),
                    "max": float(np.max(valid_values)),
                    "mean": float(np.mean(valid_values)),
                    "std": float(np.std(valid_values)),
                    "median": float(np.median(valid_values))
                })
            
            # Add feature definition if available
            if name in FEATURE_CATALOG:
                defn = FEATURE_CATALOG[name]
                feature_meta["definition"] = {
                    "description": defn.description,
                    "formula": defn.formula,
                    "unit": defn.unit,
                    "group": defn.group.value
                }
            
            # Add baseline stats if available
            if baseline_stats and name in baseline_stats:
                feature_meta["baseline"] = baseline_stats[name]
            
            metadata["features"][name] = feature_meta
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Exported JSON metadata to {filepath}")
    
    def export_all(
        self,
        features: Dict[str, np.ndarray],
        baseline_stats: Optional[Dict[str, Dict[str, float]]] = None,
        prefix: str = "features"
    ):
        """
        Export features in all formats.
        
        Args:
            features: Dictionary of feature name -> values
            baseline_stats: Baseline statistics if available
            prefix: Prefix for output filenames
        """
        self.export_csv(features, f"{prefix}.csv")
        self.export_numpy(features, f"{prefix}.npz")
        self.export_json(features, baseline_stats, f"{prefix}_metadata.json")
    
    def get_current_state(
        self,
        features: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Get current state as JSON (for real-time agent integration).
        
        Args:
            features: Dictionary of feature name -> values
            
        Returns:
            Dictionary with latest feature values
        """
        state = {}
        
        for name, values in features.items():
            if len(values) > 0:
                # Get latest non-NaN value
                valid_indices = np.where(~np.isnan(values))[0]
                if len(valid_indices) > 0:
                    latest_idx = valid_indices[-1]
                    state[name] = float(values[latest_idx])
                else:
                    state[name] = None
            else:
                state[name] = None
        
        return state
    
    def get_anomalies(
        self,
        features: Dict[str, np.ndarray],
        baseline_stats: Dict[str, Dict[str, float]],
        threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Get features with z-score above threshold (anomalies).
        
        Args:
            features: Dictionary of feature name -> values
            baseline_stats: Baseline statistics
            threshold: Z-score threshold
            
        Returns:
            List of anomalies with feature name, value, and z-score
        """
        anomalies = []
        
        for name, values in features.items():
            if name == 'timestamp' or '_zscore' in name:
                continue
            
            if name not in baseline_stats:
                continue
            
            stats = baseline_stats[name]
            if stats['std'] == 0:
                continue
            
            # Get latest valid value
            valid_indices = np.where(~np.isnan(values))[0]
            if len(valid_indices) == 0:
                continue
            
            latest_idx = valid_indices[-1]
            latest_value = values[latest_idx]
            
            # Compute z-score
            zscore = (latest_value - stats['mean']) / stats['std']
            
            if abs(zscore) >= threshold:
                anomalies.append({
                    'feature': name,
                    'value': float(latest_value),
                    'zscore': float(zscore),
                    'baseline_mean': stats['mean'],
                    'baseline_std': stats['std']
                })
        
        # Sort by absolute z-score (highest first)
        anomalies.sort(key=lambda x: abs(x['zscore']), reverse=True)
        
        return anomalies


def load_numpy_features(filepath: str) -> Dict[str, Any]:
    """
    Load features from NumPy file.
    
    Args:
        filepath: Path to .npz file
        
    Returns:
        Dictionary with feature_matrix, feature_names, timestamps
    """
    data = np.load(filepath)
    return {
        'feature_matrix': data['feature_matrix'],
        'feature_names': data['feature_names'].tolist(),
        'timestamps': data['timestamps']
    }


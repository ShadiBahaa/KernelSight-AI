#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
KernelSight API Server - FastAPI Backend

REST API for KernelSight AI web dashboard.

Endpoints:
- GET /api/signals - Query system signals
- GET /api/agent/status - Get agent status
- GET /api/agent/history - Get agent decision history
- GET /api/stats - Get system statistics
- POST /api/predict - Run prediction
- GET /api/health - Health check
- GET /api/diagnostics - System diagnostics

Run:
    uvicorn api_server:app --reload --port 8000
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from pipeline.db_manager import DatabaseManager
    from agent.agent_tools import AgentTools
except ImportError as e:
    print(f"Warning: Could not import KernelSight modules: {e}")
    DatabaseManager = None
    AgentTools = None

# Initialize FastAPI
app = FastAPI(
    title="KernelSight AI API",
    description="Autonomous SRE System - REST API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = Path(__file__).parent / "data" / "kernelsight.db"


# Pydantic models
class SignalQuery(BaseModel):
    signal_type: Optional[str] = None
    severity: Optional[str] = None
    limit: int = 20
    lookback_minutes: int = 10


class PredictionRequest(BaseModel):
    signal_type: str
    duration_minutes: int = 30
    custom_slope: Optional[float] = None


# Helper to get DB connection
def get_db():
    """Get database connection"""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database not found. Is the system running?")
    return DatabaseManager(str(DB_PATH))


def get_tools():
    """Get agent tools"""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database not found. Is the system running?")
    return AgentTools(str(DB_PATH))


# ============================================
# ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "KernelSight AI API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        db_exists = DB_PATH.exists()
        
        if db_exists:
            db = get_db()
            signal_count = db.conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
        else:
            signal_count = 0
        
        return {
            "status": "healthy" if db_exists else "degraded",
            "database": "connected" if db_exists else "not found",
            "signal_count": signal_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals")
async def get_signals(
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    severity: Optional[str] = Query(None, description="Minimum severity level"),
    limit: int = Query(20, ge=1, le=1000, description="Max results"),
    lookback_minutes: int = Query(10, ge=1, le=1440, description="Lookback window in minutes")
):
    """
    Query system signals
    
    Returns recent signal data with optional filtering.
    """
    try:
        tools = get_tools()
        
        # Build query params
        params = {
            'limit': limit,
            'lookback_minutes': lookback_minutes
        }
        
        if signal_type:
            params['signal_types'] = [signal_type]
        if severity:
            params['severity_min'] = severity
        
        result = tools.query_signals(**params)
        
        # Format timestamps for JSON
        for sig in result.get('signals', []):
            sig['timestamp_iso'] = datetime.fromtimestamp(
                sig['timestamp'] / 1_000_000_000
            ).isoformat()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """
    Get system statistics
    
    Returns aggregate stats about signals and system health.
    """
    try:
        db = get_db()
        # Total signals
        total = db.conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
        
        # Signals by type
        by_type = db.conn.execute("""
            SELECT signal_type, COUNT(*) as count
            FROM signal_metadata
            GROUP BY signal_type
            ORDER BY count DESC
        """).fetchall()
        
        # Recent signals (last hour)
        cutoff = (datetime.now().timestamp() - 3600) * 1_000_000_000
        recent = db.conn.execute("""
            SELECT COUNT(*) FROM signal_metadata
            WHERE timestamp > ?
        """, (cutoff,)).fetchone()[0]
        
        # Severity distribution
        by_severity = db.conn.execute("""
            SELECT severity, COUNT(*) as count
            FROM signal_metadata
            WHERE timestamp > ?
            GROUP BY severity
        """, (cutoff,)).fetchall()
        
        return {
            "total_signals": total,
            "recent_signals": recent,
            "by_type": [{"signal_type": t, "count": c} for t, c in by_type],
            "by_severity": [{"severity": s, "count": c} for s, c in by_severity],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/status")
async def get_agent_status():
    """
    Get agent status
    
    Returns current agent state and recent activity.
    """
    try:
        agent_log = Path(__file__).parent / "logs" / "production" / "agent.log"
        
        if not agent_log.exists():
            return {
                "status": "offline",
                "message": "Agent log not found. System may not be running.",
                "activity": []
            }
        
        # Parse recent activity
        with open(agent_log, 'r') as f:
            lines = f.readlines()[-50:]
        
        activity = []
        current_phase = None
        
        for line in lines:
            for phase in ['OBSERVE', 'EXPLAIN', 'SIMULATE', 'DECIDE', 'EXECUTE', 'VERIFY']:
                if f'[{phase}]' in line:
                    current_phase = phase
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        activity.append({
                            'phase': phase,
                            'timestamp': parts[0].strip(),
                            'message': parts[-1].strip()
                        })
        
        return {
            "status": "active" if current_phase else "idle",
            "current_phase": current_phase,
            "activity": activity[-20:],  # Last 20 events
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/history")
async def get_agent_history(
    limit: int = Query(10, ge=1, le=100, description="Number of iterations to return")
):
    """
    Get agent decision history
    
    Returns history of agent decisions and actions.
    """
    try:
        agent_log = Path(__file__).parent / "logs" / "production" / "agent.log"
        
        if not agent_log.exists():
            return {"iterations": []}
        
        # Parse iterations from log
        with open(agent_log, 'r') as f:
            lines = f.readlines()
        
        iterations = []
        current_iteration = None
        
        for line in lines:
            if 'Starting autonomous analysis' in line:
                if current_iteration:
                    iterations.append(current_iteration)
                current_iteration = {
                    'timestamp': line.split(' - ')[0].strip() if ' - ' in line else None,
                    'phases': {}
                }
            elif current_iteration:
                for phase in ['OBSERVE', 'EXPLAIN', 'SIMULATE', 'DECIDE', 'EXECUTE', 'VERIFY']:
                    if f'[{phase}]' in line:
                        message = line.split(' - ')[-1].strip() if ' - ' in line else line.strip()
                        if phase not in current_iteration['phases']:
                            current_iteration['phases'][phase] = []
                        current_iteration['phases'][phase].append(message)
        
        if current_iteration:
            iterations.append(current_iteration)
        
        return {
            "iterations": iterations[-limit:],
            "count": len(iterations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
async def run_prediction(request: PredictionRequest):
    """
    Run counterfactual prediction
    
    Simulates future system state based on current trends.
    """
    try:
        tools = get_tools()
        
        result = tools.simulate_scenario(
            signal_type=request.signal_type,
            duration_minutes=request.duration_minutes,
            custom_slope=request.custom_slope
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/diagnostics")
async def run_diagnostics():
    """
    Run system diagnostics
    
    Checks database, eBPF tracers, logs, and agent status.
    """
    try:
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "checks": []
        }
        
        # Check 1: Database
        db_check = {"component": "Database", "status": "ok", "details": []}
        try:
            if DB_PATH.exists():
                size_mb = DB_PATH.stat().st_size / (1024 * 1024)
                db_check["details"].append(f"Size: {size_mb:.2f} MB")
                
                db = get_db()
                signal_count = db.conn.execute("SELECT COUNT(*) FROM signal_metadata").fetchone()[0]
                db_check["details"].append(f"Signals: {signal_count:,}")
            else:
                db_check["status"] = "error"
                db_check["details"].append("Database not found")
        except Exception as e:
            db_check["status"] = "error"
            db_check["details"].append(f"Error: {str(e)}")
        
        diagnostics["checks"].append(db_check)
        
        # Check 2: eBPF Tracers
        ebpf_check = {"component": "eBPF Tracers", "status": "ok", "details": []}
        build_dir = Path(__file__).parent / "build" / "src" / "telemetry"
        
        tracers = ['syscall_tracer', 'sched_tracer', 'page_fault_tracer', 'io_latency_tracer']
        found = sum(1 for t in tracers if (build_dir / t).exists())
        
        ebpf_check["details"].append(f"{found}/{len(tracers)} tracers found")
        if found < len(tracers):
            ebpf_check["status"] = "warning"
        
        diagnostics["checks"].append(ebpf_check)
        
        # Check 3: Agent
        agent_check = {"component": "Agent", "status": "ok", "details": []}
        agent_log = Path(__file__).parent / "logs" / "production" / "agent.log"
        
        if agent_log.exists():
            agent_check["details"].append("Log file exists")
            size_kb = agent_log.stat().st_size / 1024
            agent_check["details"].append(f"Log size: {size_kb:.1f} KB")
        else:
            agent_check["status"] = "warning"
            agent_check["details"].append("Log file not found")
        
        diagnostics["checks"].append(agent_check)
        
        # Overall status
        statuses = [c["status"] for c in diagnostics["checks"]]
        if "error" in statuses:
            diagnostics["overall_status"] = "error"
        elif "warning" in statuses:
            diagnostics["overall_status"] = "warning"
        else:
            diagnostics["overall_status"] = "healthy"
        
        return diagnostics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url)}
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    print("Starting KernelSight API Server...")
    print("API Docs: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/api/health")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

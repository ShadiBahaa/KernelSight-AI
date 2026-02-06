#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
KernelSight AI - Production Orchestrator

This is the MAIN production script that orchestrates the entire KernelSight AI system:
  1. eBPF tracers (syscall, scheduler, page_fault, io_latency) - Real-time kernel events
  2. Scraper daemon - System-wide metrics (CPU, memory, disk, network)
  3. Semantic ingestion daemon - Converts raw data → semantic signals
  4. Autonomous agent - Monitors signals and takes remediation actions

All components run in parallel with proper data flow and logging.
"""

import sys
import os
import argparse
import subprocess
import signal
import time
import logging
import getpass
from pathlib import Path
from threading import Thread, Event
import queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.resolve()
BUILD_DIR = PROJECT_ROOT / "build" / "src" / "telemetry"
SRC_DIR = PROJECT_ROOT / "src"

# Add src to path
sys.path.insert(0, str(SRC_DIR))

# Virtual environment path - use home directory to avoid shared folder issues
VENV_DIR = Path.home() / ".config" / "kernelsight" / "venv"
VENV_PYTHON = VENV_DIR / "bin" / "python3"
VENV_PIP = VENV_DIR / "bin" / "pip"


def setup_virtual_environment(agent_enabled: bool) -> bool:
    """
    Automatically set up virtual environment and install dependencies.
    Returns True if successful, False otherwise.
    """
    if not agent_enabled:
        return True
    
    # Check if we're already in the venv
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    # Check if dependencies are available
    try:
        from google import genai
        return True  # All good!
    except ImportError:
        pass
    
    # If in venv but missing deps, install them
    if in_venv:
        logger.info("Installing agent dependencies in virtual environment...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'google-genai>=1.55.0'], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("✓ Dependencies installed")
            return True
        except subprocess.CalledProcessError:
            logger.error("Failed to install dependencies")
            return False
    
    # Not in venv - need to create one
    logger.info("=" * 60)
    logger.info("Setting up virtual environment for agent dependencies")
    logger.info("=" * 60)
    logger.info("")
    
    # Remove broken venv if it exists
    if VENV_DIR.exists():
        if not VENV_PYTHON.exists():
            logger.info(f"Removing broken virtual environment...")
            import shutil
            shutil.rmtree(VENV_DIR)
    
    # Create venv if it doesn't exist
    if not VENV_DIR.exists():
        logger.info(f"Creating virtual environment at {VENV_DIR}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', str(VENV_DIR)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("✓ Virtual environment created")
            
            # Bootstrap pip in the venv
            logger.info("Bootstrapping pip...")
            subprocess.check_call([str(VENV_PYTHON), '-m', 'ensurepip', '--upgrade'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("✓ Pip installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create venv: {e}")
            logger.error("Install with: sudo apt install python3-venv python3-full")
            return False
    
    # Install dependencies using python -m pip for reliability
    logger.info("Installing agent dependencies...")
    try:
        # Show errors for debugging
        result = subprocess.run([str(VENV_PYTHON), '-m', 'pip', 'install', 'google-genai>=1.55.0'],
                            capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Pip install failed:")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
        logger.info("✓ Dependencies installed")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to install dependencies")
        return False
    
    # Re-execute script in venv context
    logger.info("")
    logger.info("Restarting with virtual environment...")
    logger.info("")
    
    # Preserve all arguments
    venv_args = [str(VENV_PYTHON)] + sys.argv
    
    # If running with sudo, preserve environment
    if os.geteuid() == 0:
        os.execv(str(VENV_PYTHON), venv_args)
    else:
        # Add sudo if needed (for eBPF tracers)
        logger.info("Note: You may need to run with sudo for eBPF tracers")
        os.execv(str(VENV_PYTHON), venv_args)
    
    return False  # Won't reach here



def prompt_for_api_key() -> bool:
    """
    Prompt user for Gemini API key if not set in environment.
    Returns True if key is available, False otherwise.
    """
    # Check if already set
    existing_key = os.environ.get('GEMINI_API_KEY')
    if existing_key:
        logger.info("")
        logger.info("✓ GEMINI_API_KEY already set in environment")
        logger.info("")
        return True
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Gemini API Key Required for Autonomous Agent")
    logger.info("=" * 60)
    logger.info("")
    logger.info("The autonomous agent uses Google's Gemini API.")
    logger.info("Get your free API key at: https://aistudio.google.com/app/apikey")
    logger.info("")
    
    try:
        api_key = getpass.getpass("Enter your Gemini API key (input hidden): ").strip()
        
        if not api_key:
            logger.warning("No API key provided.")
            return False
        
        # Set in environment for this process
        os.environ['GEMINI_API_KEY'] = api_key
        logger.info("✓ API key configured")
        logger.info("")
        return True
    
    except (KeyboardInterrupt, EOFError):
        logger.warning("\nAPI key input cancelled.")
        return False


class ProcessManager:
    """Manages all KernelSight AI processes."""
    
    def __init__(self, db_path: str, agent_enabled: bool = True, agent_interval: int = 60):
        self.db_path = Path(db_path).resolve()
        self.agent_enabled = agent_enabled
        self.agent_interval = agent_interval
        
        self.processes = {}
        self.threads = {}
        self.stop_event = Event()
        self.event_queue = queue.Queue(maxsize=10000)
        
        # Log directory
        self.log_dir = PROJECT_ROOT / "logs" / "production"
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def verify_build_artifacts(self):
        """Verify all required binaries exist."""
        logger.info("Verifying build artifacts...")
        
        required_bins = {
            'syscall_tracer': BUILD_DIR / 'syscall_tracer',
            'sched_tracer': BUILD_DIR / 'sched_tracer',
            'page_fault_tracer': BUILD_DIR / 'page_fault_tracer',
            'io_latency_tracer': BUILD_DIR / 'io_latency_tracer',
            'scraper_daemon': BUILD_DIR / 'scraper_daemon'
        }
        
        missing = []
        for name, path in required_bins.items():
            if not path.exists():
                missing.append(name)
            else:
                logger.info(f"  ✓ {name}")
        
        if missing:
            logger.error(f"Missing binaries: {', '.join(missing)}")
            logger.error("Please build the project first:")
            logger.error(f"  cd {PROJECT_ROOT} && mkdir -p build && cd build && cmake .. && make")
            sys.exit(1)
        
        logger.info("✓ All binaries found")
    
    def initialize_database(self):
        """Initialize the database schema."""
        logger.info(f"Initializing database: {self.db_path}")
        
        from pipeline.semantic_ingestion_daemon import SemanticIngestionDaemon
        
        # Create database directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        from pipeline.db_manager import DatabaseManager
        db = DatabaseManager(str(self.db_path))
        db.init_schema()
        db.close()
        
        logger.info("✓ Database initialized")
    
    def start_ebpf_tracer(self, name: str, binary: str):
        """Start an eBPF tracer and stream output to queue."""
        log_file = self.log_dir / f"{name}.log"
        
        def reader_thread():
            cmd = ['sudo', f'./{binary}']
            logger.info(f"Starting {name}: {' '.join(cmd)} (cwd: {BUILD_DIR})")
            
            with open(log_file, 'w') as log:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=str(BUILD_DIR)  # Run from build directory
                    )
                    self.processes[name] = proc
                    
                    import json
                    for line in proc.stdout:
                        if self.stop_event.is_set():
                            break
                        
                        log.write(line)
                        log.flush()
                        
                        # Only queue valid JSON events
                        line = line.strip()
                        if line.startswith('{'):  # Potential JSON
                            try:
                                event = json.loads(line)
                                # Verify it has required fields
                                if isinstance(event, dict) and 'type' in event:
                                    self.event_queue.put(line, timeout=1)
                            except json.JSONDecodeError:
                                # Not valid JSON - this is normal for status/error messages
                                pass
                            except queue.Full:
                                logger.warning(f"{name}: Event queue full, dropping event")
                    
                    proc.wait()
                    if not self.stop_event.is_set():
                        logger.warning(f"{name} exited with code {proc.returncode}")
                
                except Exception as e:
                    logger.error(f"{name} error: {e}")
        
        thread = Thread(target=reader_thread, daemon=True, name=name)
        thread.start()
        self.threads[name] = thread
    
    def start_scraper(self):
        """Start the scraper daemon."""
        name = "scraper"
        log_file = self.log_dir / f"{name}.log"
        
        def reader_thread():
            cmd = [str(BUILD_DIR / 'scraper_daemon')]
            logger.info(f"Starting {name}: {' '.join(cmd)}")
            
            with open(log_file, 'w') as log:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    self.processes[name] = proc
                    
                    import json
                    for line in proc.stdout:
                        if self.stop_event.is_set():
                            break
                        
                        log.write(line)
                        log.flush()
                        
                        # Only queue valid JSON events
                        line = line.strip()
                        if line.startswith('{'):  # Potential JSON
                            try:
                                event = json.loads(line)
                                # Verify it has required fields
                                if isinstance(event, dict) and 'type' in event:
                                    self.event_queue.put(line, timeout=1)
                            except json.JSONDecodeError:
                                # Not valid JSON - this is normal for status/error messages
                                pass
                            except queue.Full:
                                logger.warning(f"{name}: Event queue full, dropping event")
                    
                    proc.wait()
                    if not self.stop_event.is_set():
                        logger.warning(f"{name} exited with code {proc.returncode}")
                
                except Exception as e:
                    logger.error(f"{name} error: {e}")
        
        thread = Thread(target=reader_thread, daemon=True, name=name)
        thread.start()
        self.threads[name] = thread
    
    def start_ingestion_daemon(self):
        """Start the semantic ingestion daemon."""
        name = "ingestion"
        log_file = self.log_dir / f"{name}.log"
        
        def ingestion_thread():
            logger.info(f"Starting semantic ingestion daemon")
            
            from pipeline.semantic_ingestion_daemon import SemanticIngestionDaemon
            
            with open(log_file, 'w') as log:
                try:
                    # Redirect logs to file
                    handler = logging.FileHandler(log_file)
                    handler.setFormatter(logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    ))
                    logging.getLogger('src.pipeline').addHandler(handler)
                    
                    daemon = SemanticIngestionDaemon(str(self.db_path))
                    
                    # Process events from queue
                    while not self.stop_event.is_set():
                        try:
                            event_line = self.event_queue.get(timeout=1)
                            
                            # Parse and process
                            import json
                            try:
                                event = json.loads(event_line)
                                daemon.process_event(event)
                            except json.JSONDecodeError as e:
                                # This shouldn't happen since we validate before queuing
                                logger.error(f"Invalid JSON from queue: {e}")
                                logger.error(f"Line: {event_line[:100]}")
                        
                        except queue.Empty:
                            continue
                    
                    # Final commit
                    daemon.db.commit()
                    daemon.print_stats()
                    daemon.db.close()
                
                except Exception as e:
                    logger.error(f"Ingestion daemon error: {e}")
                    import traceback
                    traceback.print_exc()
        
        thread = Thread(target=ingestion_thread, daemon=True, name=name)
        thread.start()
        self.threads[name] = thread
    
    def start_agent(self):
        """Start the autonomous agent."""
        if not self.agent_enabled:
            return
        
        name = "agent"
        log_file = self.log_dir / f"{name}.log"
        
        def agent_thread():
            logger.info(f"Starting autonomous agent (interval: {self.agent_interval}s)")
            
            try:
                from agent.autonomous_loop import AutonomousAgent
            except ModuleNotFoundError as e:
                logger.warning(f"Agent dependencies missing: {e}")
                logger.warning("Install with: pip install google-genai")
                logger.warning("Agent will not run, but data collection continues")
                return
            
            with open(log_file, 'w') as log:
                try:
                    # Redirect agent logs to file
                    handler = logging.FileHandler(log_file)
                    handler.setFormatter(logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    ))
                    logging.getLogger('src.agent').addHandler(handler)
                    
                    agent = AutonomousAgent(str(self.db_path))
                    iteration = 0
                    
                    while not self.stop_event.is_set():
                        iteration += 1
                        logger.info(f"[Iteration {iteration}] Starting autonomous analysis...")
                        
                        try:
                            result = agent.analyze_and_act(max_iterations=3)
                            
                            status = result.get('status', 'action_attempted')
                            action_taken = result.get('action_taken', False)
                            resolved = result.get('resolved', False)
                            
                            logger.info(f"[Iteration {iteration}] Status: {status}, "
                                      f"Action: {action_taken}, Resolved: {resolved}")
                            
                            # Log phases
                            for phase, data in result.get('phases', {}).items():
                                logger.info(f"[Iteration {iteration}] {phase.upper()}: {data}")
                        
                        except Exception as e:
                            logger.error(f"[Iteration {iteration}] Error: {e}")
                        
                        # Sleep with interruptible wait
                        for _ in range(self.agent_interval):
                            if self.stop_event.is_set():
                                break
                            time.sleep(1)
                    
                    agent.close()
                
                except Exception as e:
                    logger.error(f"Agent error: {e}")
                    import traceback
                    traceback.print_exc()
        
        thread = Thread(target=agent_thread, daemon=True, name=name)
        thread.start()
        self.threads[name] = thread
    
    def start_all(self):
        """Start all components."""
        logger.info("=" * 60)
        logger.info("KernelSight AI - Production System")
        logger.info("=" * 60)
        
        # Verify and initialize
        self.verify_build_artifacts()
        self.initialize_database()
        
        logger.info("")
        logger.info("Starting components...")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Logs: {self.log_dir}")
        logger.info("")
        
        # Start ingestion daemon first (processes events)
        self.start_ingestion_daemon()
        time.sleep(1)
        
        # Start data collectors
        self.start_ebpf_tracer('syscall', 'syscall_tracer')
        self.start_ebpf_tracer('scheduler', 'sched_tracer')
        self.start_ebpf_tracer('pagefault', 'page_fault_tracer')
        self.start_ebpf_tracer('io', 'io_latency_tracer')
        self.start_scraper()
        
        # Wait for tracers to initialize
        time.sleep(2)
        
        # Start autonomous agent
        self.start_agent()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ KernelSight AI System Running")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Running components:")
        logger.info("  [1] Syscall Tracer     - eBPF monitoring of system calls")
        logger.info("  [2] Scheduler Tracer   - eBPF monitoring of context switches")
        logger.info("  [3] Page Fault Tracer  - eBPF monitoring of memory faults")
        logger.info("  [4] I/O Latency Tracer - eBPF monitoring of disk I/O")
        logger.info("  [5] Scraper Daemon     - System metrics collection")
        logger.info("  [6] Ingestion Daemon   - Raw data → semantic signals")
        if self.agent_enabled:
            logger.info(f"  [7] Autonomous Agent   - AI monitoring (every {self.agent_interval}s)")
        logger.info("")
        logger.info("Monitoring commands:")
        logger.info(f"  View signals: sqlite3 {self.db_path} 'SELECT * FROM signal_metadata ORDER BY timestamp DESC LIMIT 10;'")
        logger.info(f"  View logs:    tail -f {self.log_dir}/*.log")
        logger.info("")
        logger.info("Press Ctrl+C to stop all components")
        logger.info("")
    
    def stop_all(self):
        """Stop all components gracefully."""
        logger.info("")
        logger.info("Stopping all components...")
        
        self.stop_event.set()
        
        # Kill processes
        for name, proc in self.processes.items():
            logger.info(f"  Stopping {name}...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        # Wait for threads
        for name, thread in self.threads.items():
            logger.info(f"  Waiting for {name} thread...")
            thread.join(timeout=5)
        
        logger.info("✓ All components stopped")
    
    def run(self):
        """Run the system until interrupted."""
        try:
            self.start_all()
            
            # Keep main thread alive
            while True:
                time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            self.stop_all()


def main():
    parser = argparse.ArgumentParser(
        description='KernelSight AI - Production System Orchestrator'
    )
    parser.add_argument(
        '--db',
        default='data/kernelsight.db',
        help='Database file path (default: data/kernelsight.db)'
    )
    parser.add_argument(
        '--no-agent',
        action='store_true',
        help='Run without autonomous agent'
    )
    parser.add_argument(
        '--agent-interval',
        type=int,
        default=60,
        help='Agent check interval in seconds (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Set up virtual environment and dependencies automatically
    agent_enabled = not args.no_agent
    env_ok = setup_virtual_environment(agent_enabled)
    
    if not env_ok:
        # Setup failed, continue without agent
        logger.warning("Could not set up agent environment")
        logger.warning("Continuing without autonomous agent...")
        logger.warning("")
        agent_enabled = False
    elif agent_enabled:
        # Environment OK, now check/prompt for API key
        if not prompt_for_api_key():
            logger.warning("Continuing without autonomous agent...")
            logger.warning("")
            agent_enabled = False
    
    # Resolve database path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    
    # Create and run orchestrator
    orchestrator = ProcessManager(
        db_path=str(db_path),
        agent_enabled=agent_enabled,
        agent_interval=args.agent_interval
    )
    
    orchestrator.run()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Semantic Ingestion Daemon

Wraps the standard ingestion daemon to add semantic signal processing.
- Reads JSON events from stdin (from eBPF tracers + scrapers)
- Stores raw events in database (original tables)
- Processes through semantic classifiers
- Stores semantic observations in signal_metadata table
"""

import sys
import json
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import database manager
from src.pipeline.db_manager import DatabaseManager

# Import semantic classifiers
from src.pipeline.signals.syscall_classifier import SyscallSemanticClassifier
from src.pipeline.signals.scheduler_classifier import SchedulerSemanticClassifier
from src.pipeline.signals.system_classifier import SystemMetricsClassifier
from src.pipeline.signals.pagefault_classifier import PageFaultSemanticClassifier

# Import signal DB adapter
from src.pipeline.signal_db_adapter import SignalDatabaseAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SemanticIngestionDaemon:
    """Ingestion daemon with semantic signal processing."""
    
    def __init__(self, db_path: str, num_cpus: int = 4):
        """
        Initialize daemon.
        
        Args:
            db_path: Path to SQLite database
            num_cpus: Number of CPU cores (for classifiers)
        """
        self.db = DatabaseManager(db_path)
        self.db.init_schema()
        
        # Initialize classifiers
        self.syscall_classifier = SyscallSemanticClassifier()
        self.scheduler_classifier = SchedulerSemanticClassifier(num_cpus=num_cpus)
        self.system_classifier = SystemMetricsClassifier(num_cpus=num_cpus)
        self.pagefault_classifier = PageFaultSemanticClassifier()
        
        # Initialize adapter
        self.adapter = SignalDatabaseAdapter(self.db)
        
        # Statistics
        self.stats = {
            'total_events': 0,
            'syscall_events': 0,
            'sched_events': 0,
            'memory_metrics': 0,
            'load_metrics': 0,
            'io_stats': 0,
            'block_stats': 0,
            'network_stats': 0,
            'tcp_stats': 0,
            'page_fault_events': 0,
            'signals_created': 0,
            'errors': 0
        }
    
    def process_event(self, event: Dict[str, Any]):
        """Process a single event: store raw + create semantic observation."""
        try:
            event_type = event.get('type', '')
            
            # Map scraper daemon event types to internal types
            type_mapping = {
                'meminfo': 'memory',
                'loadavg': 'load',
                'blockstats': 'block',
                'net_interface': 'network',
                'tcp_stats': 'tcp',
                'tcp_retransmits': 'tcp_retransmit',
                'pagefault': 'page_fault'  # Map tracer output to internal type
            }

            
            event_type = type_mapping.get(event_type, event_type)
            
            # Store raw event and get ID
            source_id = None
            
            if event_type == 'syscall':
                source_id = self.process_syscall(event)
                self.stats['syscall_events'] += 1
            
            elif event_type == 'sched':
                source_id = self.process_scheduler(event)
                self.stats['sched_events'] += 1
            
            elif event_type == 'memory':
                source_id = self.process_memory(event)
                self.stats['memory_metrics'] += 1
            
            elif event_type == 'load':
                source_id = self.process_load(event)
                self.stats['load_metrics'] += 1
            
            elif event_type == 'io':
                source_id = self.process_io(event)
                self.stats['io_stats'] += 1
            
            elif event_type == 'block':
                source_id = self.process_block(event)
                self.stats['block_stats'] += 1
            
            elif event_type == 'network':
                source_id = self.process_network(event)
                self.stats['network_stats'] += 1
            
            elif event_type == 'tcp':
                source_id = self.process_tcp(event)
                self.stats['tcp_stats'] += 1
            
            elif event_type == 'tcp_retransmit':
                source_id = self.process_tcp_retransmit(event)
                self.stats['tcp_stats'] += 1
            
            elif event_type == 'page_fault':
                source_id = self.process_pagefault(event)
                self.stats['page_fault_events'] += 1
            
            else:
                logger.warning(f"Unknown event type: {event_type}")
                return
            
            self.stats['total_events'] += 1
            
            # Commit after each event (could batch later)
            if self.stats['total_events'] % 100 == 0:
                self.db.commit()
                self.print_stats()  # Print stats every 100 events

        
        except Exception as e:
            import traceback
            logger.error(f"Error processing event: {e}")
            logger.debug(traceback.format_exc())
            self.stats['errors'] += 1
    
    def process_syscall(self, event: Dict) -> int:
        """Process syscall event."""
        source_id = self.db.insert_syscall_event(event)
        
        # Create semantic observation
        try:
            obs = self.syscall_classifier.create_observation(event)
            self.adapter.store_syscall_observation(obs, source_id)
            self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing syscall signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_scheduler(self, event: Dict) -> int:
        """Process scheduler event."""
        source_id = self.db.insert_sched_event(event)
        
        # Create semantic observation
        try:
            obs = self.scheduler_classifier.create_observation(event)
            # Only create signal if not "normal"
            if obs.state.value != 'normal':
                self.adapter.store_scheduler_observation(obs, source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            logger.debug(f"No semantic signal for scheduler: {e}")
        
        return source_id
    
    def process_memory(self, event: Dict) -> int:
        """Process memory metrics."""
        # Merge timestamp with nested data fields
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp')}
        source_id = self.db.insert_memory_metrics(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'memory_metrics', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_load(self, event: Dict) -> int:
        """Process load metrics."""
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp')}
        source_id = self.db.insert_load_metrics(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'load_metrics', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing load signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_io(self, event: Dict) -> int:
        """Process I/O stats."""
        source_id = self.db.insert_io_latency_stats(event)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(event, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'io_latency_stats', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing IO signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_block(self, event: Dict) -> int:
        """Process block stats."""
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp'), 'device': event.get('device')}
        source_id = self.db.insert_block_stats(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'block_stats', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing block signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_network(self, event: Dict) -> int:
        """Process network stats."""
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp'), 'interface': event.get('interface')}
        source_id = self.db.insert_network_stats(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'network_interface_stats', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing network signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_tcp(self, event: Dict) -> int:
        """Process TCP stats."""
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp')}
        source_id = self.db.insert_tcp_stats(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'tcp_stats', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing TCP signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_tcp_retransmit(self, event: Dict) -> int:
        """Process TCP retransmit stats."""
        metrics = {**event.get('data', {}), 'timestamp': event.get('timestamp')}
        source_id = self.db.insert_tcp_retransmit_stats(metrics)
        
        # Create semantic observation via system classifier
        try:
            obs = self.system_classifier.create_observation(metrics, timestamp=event.get('timestamp', 0))
            if obs.pressure_type.value != 'none':
                self.adapter.store_system_observation(obs, 'tcp_retransmit_stats', source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            import traceback
            logger.error(f"ERROR storing TCP retransmit signal: {e}")
            logger.error(traceback.format_exc())
        
        return source_id
    
    def process_pagefault(self, event: Dict) -> int:
        """Process page fault event."""
        source_id = self.db.insert_page_fault_event(event)
        
        # Create semantic observation
        try:
            obs = self.pagefault_classifier.create_observation(event)
            # Only create signal for major faults or high severity
            if obs.severity.value in ('medium', 'high', 'critical'):
                signal_id = self.adapter.store_pagefault_observation(obs, source_id)
                self.stats['signals_created'] += 1
        except Exception as e:
            logger.debug(f"No semantic signal for page fault: {e}")
        
        return source_id
    
    def print_stats(self):
        """Print processing statistics."""
        logger.info(f"Stats: {self.stats['total_events']} events processed, "
                   f"{self.stats['signals_created']} semantic signals created, "
                   f"{self.stats['errors']} errors")
    
    def run(self):
        """Main event loop - read from stdin."""
        logger.info("Semantic ingestion daemon starting...")
        logger.info("Reading JSON events from stdin...")
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                
                # Skip non-JSON lines (like tail's "==> file <==" headers)
                if not line.startswith('{'):
                    continue
                
                # Each line should be a complete JSON object
                # Try to parse directly without buffering
                try:
                    event = json.loads(line)
                    
                    # Only process if it has a type field
                    if isinstance(event, dict) and 'type' in event:
                        self.process_event(event)
                    else:
                        logger.debug(f"Skipping event without type field: {str(event)[:50]}")
                except json.JSONDecodeError as e:
                    # Log error but don't buffer - each line should be complete
                    logger.warning(f"Invalid JSON (skipping): {line[:80]}... Error: {e}")
                    self.stats['errors'] += 1
        

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            self.db.commit()
            self.print_stats()
            logger.info("Final stats:")
            for key, value in sorted(self.stats.items()):
                logger.info(f"  {key}: {value}")
            
            # Show signal counts
            signal_count = self.db.conn.execute(
                "SELECT COUNT(*) FROM signal_metadata"
            ).fetchone()[0]
            logger.info(f"Total signals in database: {signal_count}")
            
            self.db.close()
    
    def run_tail_files(self, file_paths):
        """
        Watch multiple files using subprocess tail -F with threading.
        Each file gets its own thread for blocking reads.
        """
        import subprocess
        import threading
        import queue
        import os
        
        logger.info("Semantic ingestion daemon starting (tail -F threaded mode)...")
        logger.info(f"Tailing {len(file_paths)} files: {file_paths}")
        
        # Map filenames to event types
        type_from_filename = {
            'syscall': 'syscall',
            'scheduler': 'sched',
            'pagefault': 'page_fault',
            'io': 'io',
            'scraper': None  # Scraper events have their own type field
        }
        
        # Shared queue for events from all threads
        event_queue = queue.Queue()
        stop_event = threading.Event()
        
        def tail_worker(path: str, default_type: str):
            """Worker thread that tails a single file."""
            try:
                if not os.path.exists(path):
                    open(path, 'a').close()
                
                # Start tail -F process
                proc = subprocess.Popen(
                    ['tail', '-F', '-n', '0', path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=1,
                    universal_newlines=True
                )
                logger.info(f"  Thread started for: {path}")
                
                while not stop_event.is_set():
                    line = proc.stdout.readline()  # Blocking read
                    if not line:
                        if proc.poll() is not None:
                            logger.warning(f"Tail process died for {path}")
                            break
                        continue
                    
                    line = line.strip()
                    if line and line.startswith('{'):
                        event_queue.put((line, default_type))
                
                proc.terminate()
                
            except Exception as e:
                logger.error(f"Error in tail worker for {path}: {e}")
        
        # Start a thread for each file
        threads = []
        for path in file_paths:
            filename = os.path.basename(path).replace('.log', '')
            default_type = type_from_filename.get(filename)
            t = threading.Thread(target=tail_worker, args=(path, default_type), daemon=True)
            t.start()
            threads.append(t)
        
        try:
            # Main loop to process events from all threads
            while True:
                try:
                    # Get event from queue with timeout
                    line, default_type = event_queue.get(timeout=0.5)
                    
                    try:
                        event = json.loads(line)
                        if isinstance(event, dict):
                            if 'type' not in event and default_type:
                                event['type'] = default_type
                            
                            if 'type' in event:
                                self.process_event(event)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON: {line[:60]}... Error: {e}")
                        self.stats['errors'] += 1
                    
                    # Print stats periodically
                    if self.stats['total_events'] > 0 and self.stats['total_events'] % 100 == 0:
                        self.print_stats()
                        
                except queue.Empty:
                    # No events, just continue
                    pass
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            stop_event.set()
            self.db.commit()
            self.print_stats()
            self.db.close()
    
    def run_watch_files(self, file_paths):
        """
        Watch multiple files and process JSON events from them.
        This version handles VirtualBox shared folder issues by reopening files.
        """
        import os
        
        logger.info("Semantic ingestion daemon starting (file watch mode)...")
        logger.info(f"Watching {len(file_paths)} files: {file_paths}")
        
        # Track file positions (byte offsets) - NOT file handles
        file_positions = {}
        
        for path in file_paths:
            try:
                # Create file if it doesn't exist
                if not os.path.exists(path):
                    open(path, 'a').close()
                # Get initial file size to start from end
                file_positions[path] = os.path.getsize(path)
                logger.info(f"  Watching: {path} (starting at byte {file_positions[path]})")
            except Exception as e:
                logger.error(f"Cannot access {path}: {e}")
        
        if not file_positions:
            logger.error("No files to watch!")
            return
        
        # Map filenames to event types
        type_from_filename = {
            'syscall': 'syscall',
            'scheduler': 'sched',
            'pagefault': 'page_fault',
            'io': 'io',
            'scraper': None  # Scraper events have their own type field
        }
        
        try:
            while True:
                events_this_round = 0
                
                # Read from each file
                for path in list(file_positions.keys()):
                    try:
                        # Check current file size via os.path.getsize (works on VirtualBox)
                        current_size = os.path.getsize(path)
                        prev_pos = file_positions[path]
                        
                        if current_size > prev_pos:
                            # New content available - reopen file and read from position
                            filename = os.path.basename(path).replace('.log', '')
                            default_type = type_from_filename.get(filename)
                            
                            with open(path, 'r') as fh:
                                fh.seek(prev_pos)
                                
                                while True:
                                    line = fh.readline()
                                    if not line:
                                        break
                                    
                                    # Update position
                                    file_positions[path] = fh.tell()
                                    
                                    line = line.strip()
                                    if not line or not line.startswith('{'):
                                        continue
                                    
                                    try:
                                        event = json.loads(line)
                                        if isinstance(event, dict):
                                            # Infer type from filename if not present
                                            if 'type' not in event and default_type:
                                                event['type'] = default_type
                                            
                                            if 'type' in event:
                                                self.process_event(event)
                                                events_this_round += 1
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"Invalid JSON from {path}: {line[:60]}... Error: {e}")
                                        self.stats['errors'] += 1
                        
                        elif current_size < prev_pos:
                            # File was truncated, reset position
                            file_positions[path] = 0
                            logger.info(f"File {path} was truncated, resetting position")
                            
                    except Exception as e:
                        logger.error(f"Error reading {path}: {e}")
                

                # Print stats periodically
                if self.stats['total_events'] > 0 and self.stats['total_events'] % 100 == 0:
                    self.print_stats()
                
                # Small sleep to avoid busy-waiting
                if events_this_round == 0:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            self.db.commit()
            self.print_stats()
            self.db.close()



def main():
    parser = argparse.ArgumentParser(description='Semantic Ingestion Daemon')
    parser.add_argument('--db-path', default='data/stress_test.db',
                       help='Path to SQLite database')
    parser.add_argument('--num-cpus', type=int, default=4,
                       help='Number of CPU cores')
    parser.add_argument('--init-only', action='store_true',
                       help='Initialize database and exit')
    parser.add_argument('--watch-files', nargs='+', default=None,
                       help='Watch these files instead of reading stdin')
    
    args = parser.parse_args()
    
    if args.init_only:
        db = DatabaseManager(args.db_path)
        db.init_schema()
        db.close()
        logger.info(f"Database initialized: {args.db_path}")
        return
    
    daemon = SemanticIngestionDaemon(args.db_path, args.num_cpus)
    
    if args.watch_files:
        # Use tail -F mode for VirtualBox shared folder compatibility
        daemon.run_tail_files(args.watch_files)
    else:
        daemon.run()


if __name__ == '__main__':
    main()

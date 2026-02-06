#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 KernelSight AI
"""
Ingestion daemon for KernelSight AI telemetry pipeline.
Reads JSON events from stdin and stores them in SQLite database.
"""

import sys
import signal
import logging
import argparse
import time
import json
from collections import defaultdict
from typing import Dict, List

from db_manager import DatabaseManager
from event_parsers import (
    parse_json_line, normalize_event, EventType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)


class IngestionDaemon:
    """Main ingestion daemon that processes events and stores to database."""
    
    def __init__(self, db_path: str, batch_size: int = 100, batch_timeout: float = 1.0):
        """
        Initialize ingestion daemon.
        
        Args:
            db_path: Path to SQLite database
            batch_size: Number of events to batch before commit
            batch_timeout: Seconds to wait before forcing commit
        """
        self.db = DatabaseManager(db_path)
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.running = True
        
        # Event batches by type
        self.batches: Dict[str, List] = defaultdict(list)
        self.batch_count = 0
        self.last_commit_time = time.time()
        
        # Statistics
        self.stats = {
            'total_events': 0,
            'parse_errors': 0,
            'insert_errors': 0,
            'commits': 0,
            'events_by_type': defaultdict(int)
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def init_database(self):
        """Initialize database schema."""
        logger.info("Initializing database schema...")
        self.db.init_schema()
        logger.info("Database schema initialized")
    
    def _insert_event(self, event_type: str, event: Dict):
        """
        Insert event into appropriate table.
        
        Args:
            event_type: Type of event
            event: Normalized event data
        """
        try:
            if event_type == EventType.SYSCALL:
                self.db.insert_syscall_event(event)
            elif event_type == EventType.PAGE_FAULT:
                self.db.insert_page_fault_event(event)
            elif event_type == EventType.IO_LATENCY:
                self.db.insert_io_latency_stats(event)
            elif event_type == EventType.MEMORY:
                self.db.insert_memory_metrics(event)
            elif event_type == EventType.LOAD:
                self.db.insert_load_metrics(event)
            elif event_type == EventType.BLOCK:
                self.db.insert_block_stats(event)
            elif event_type == EventType.NETWORK:
                self.db.insert_network_stats(event)
            elif event_type == EventType.TCP:
                self.db.insert_tcp_stats(event)
            elif event_type == EventType.TCP_RETRANS:
                self.db.insert_tcp_retransmit_stats(event)
            elif event_type == EventType.SCHED:
                self.db.insert_sched_stats(event)
            else:
                logger.warning(f"Unknown event type for insertion: {event_type}")
                return
            
            self.batch_count += 1
            self.stats['events_by_type'][event_type] += 1
        
        except Exception as e:
            logger.error(f"Failed to insert {event_type} event: {e}")
            self.stats['insert_errors'] += 1
    
    def _should_commit(self) -> bool:
        """Check if we should commit the current batch."""
        if self.batch_count >= self.batch_size:
            return True
        
        elapsed = time.time() - self.last_commit_time
        if elapsed >= self.batch_timeout and self.batch_count > 0:
            return True
        
        return False
    
    def _commit_batch(self):
        """Commit current batch to database."""
        if self.batch_count == 0:
            return
        
        try:
            self.db.commit()
            self.stats['commits'] += 1
            
            logger.debug(f"Committed batch of {self.batch_count} events "
                        f"(total: {self.stats['total_events']})")
            
            self.batch_count = 0
            self.last_commit_time = time.time()
        
        except Exception as e:
            logger.error(f"Failed to commit batch: {e}")
    
    def process_line(self, line: str):
        """
        Process a single JSON line.
        
        Args:
            line: JSON event string
        """
        line = line.strip()
        if not line:
            return
        
        # Parse and identify event
        result = parse_json_line(line)
        if not result:
            self.stats['parse_errors'] += 1
            return
        
        event_type, event = result
        
        # Normalize event
        normalized = normalize_event(event_type, event)
        
        # Insert event
        self._insert_event(event_type, normalized)
        
        self.stats['total_events'] += 1
        
        # Check if we should commit
        if self._should_commit():
            self._commit_batch()
    
    def run(self):
        """Main event loop - read from stdin and process events."""
        logger.info("Ingestion daemon started")
        logger.info(f"Database: {self.db.db_path}")
        logger.info(f"Batch size: {self.batch_size}, Batch timeout: {self.batch_timeout}s")
        logger.info("Reading JSON objects from stdin...")
        
        # Import JSON object reader for multi-line JSON support
        from json_reader import read_json_objects
        
        try:
            for obj in read_json_objects(sys.stdin):
                if not self.running:
                    break
                
                # Convert object back to JSON string for existing parser
                line = json.dumps(obj)
                self.process_line(line)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        
        finally:
            self._shutdown()
    
    def _shutdown(self):
        """Graceful shutdown - commit remaining events and close database."""
        logger.info("Shutting down...")
        
        # Commit any remaining events
        self._commit_batch()
        
        # Print statistics
        self._print_stats()
        
        # Close database
        self.db.close()
        
        logger.info("Shutdown complete")
    
    def _print_stats(self):
        """Print ingestion statistics."""
        logger.info("=== Ingestion Statistics ===")
        logger.info(f"Total events processed: {self.stats['total_events']}")
        logger.info(f"Parse errors: {self.stats['parse_errors']}")
        logger.info(f"Insert errors: {self.stats['insert_errors']}")
        logger.info(f"Commits: {self.stats['commits']}")
        
        logger.info("\nEvents by type:")
        for event_type, count in sorted(self.stats['events_by_type'].items()):
            logger.info(f"  {event_type}: {count}")
        
        # Show table statistics
        logger.info("\nDatabase table sizes:")
        table_stats = self.db.get_table_stats()
        for table, count in sorted(table_stats.items()):
            if count > 0:
                logger.info(f"  {table}: {count} rows")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="KernelSight AI Ingestion Daemon",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--db-path',
        default='data/kernelsight.db',
        help='Path to SQLite database file'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of events to batch before commit'
    )
    
    parser.add_argument(
        '--batch-timeout',
        type=float,
        default=1.0,
        help='Seconds to wait before forcing commit'
    )
    
    parser.add_argument(
        '--init-only',
        action='store_true',
        help='Initialize database schema and exit'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create daemon
    daemon = IngestionDaemon(
        db_path=args.db_path,
        batch_size=args.batch_size,
        batch_timeout=args.batch_timeout
    )
    
    # Initialize schema
    daemon.init_database()
    
    if args.init_only:
        logger.info("Database initialized, exiting as requested")
        daemon.db.close()
        return 0
    
    # Run main event loop
    daemon.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

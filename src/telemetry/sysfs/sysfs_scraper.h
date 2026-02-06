// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Sysfs scraper for /sys/block/*/stat

#ifndef SYSFS_SCRAPER_H
#define SYSFS_SCRAPER_H

#include <stdint.h>

// Block device statistics from /sys/block/[device]/stat
// See: https://www.kernel.org/doc/Documentation/block/stat.txt
struct block_stats {
    uint64_t read_ios;      // Number of read I/Os processed
    uint64_t read_merges;   // Number of read I/Os merged with in-queue I/O
    uint64_t read_sectors;  // Number of sectors read
    uint64_t read_ticks;    // Total wait time for read requests (ms)
    uint64_t write_ios;     // Number of write I/Os processed
    uint64_t write_merges;  // Number of write I/Os merged with in-queue I/O
    uint64_t write_sectors; // Number of sectors written
    uint64_t write_ticks;   // Total wait time for write requests (ms)
    uint64_t in_flight;     // Number of I/Os currently in flight
    uint64_t io_ticks;      // Total time this block device has been active (ms)
    uint64_t time_in_queue; // Total wait time for all requests (ms)
};

/**
 * Discover all block devices in /sys/block/
 * @param devices Output array of device names (caller must free with free_block_devices)
 * @param count Output number of devices found
 * @return 0 on success, -1 on error
 */
int discover_block_devices(char ***devices, int *count);

/**
 * Read block device statistics from /sys/block/[device]/stat
 * @param device Device name (e.g., "sda")
 * @param stats Output structure for block statistics
 * @return 0 on success, -1 on error
 */
int read_block_stats(const char *device, struct block_stats *stats);

/**
 * Print block stats as JSON to stdout
 * @param device Device name
 * @param stats Block statistics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_block_stats_json(const char *device, const struct block_stats *stats,
                            uint64_t timestamp);

/**
 * Free memory allocated by discover_block_devices
 * @param devices Array of device names
 * @param count Number of devices
 */
void free_block_devices(char **devices, int count);

#endif // SYSFS_SCRAPER_H

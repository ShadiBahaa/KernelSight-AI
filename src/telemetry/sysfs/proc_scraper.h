// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Procfs scraper for /proc/meminfo and /proc/loadavg

#ifndef PROC_SCRAPER_H
#define PROC_SCRAPER_H

#include <stdint.h>

// Memory information from /proc/meminfo
struct meminfo_metrics {
    uint64_t mem_total_kb;
    uint64_t mem_free_kb;
    uint64_t mem_available_kb;
    uint64_t buffers_kb;
    uint64_t cached_kb;
    uint64_t swap_total_kb;
    uint64_t swap_free_kb;
    uint64_t active_kb;
    uint64_t inactive_kb;
    uint64_t dirty_kb;
    uint64_t writeback_kb;
};

// Load average from /proc/loadavg
struct loadavg_metrics {
    double load_1min;
    double load_5min;
    double load_15min;
    uint32_t running_processes;
    uint32_t total_processes;
    uint32_t last_pid;
};

/**
 * Read and parse /proc/meminfo
 * @param metrics Output structure for memory metrics
 * @return 0 on success, -1 on error
 */
int read_proc_meminfo(struct meminfo_metrics *metrics);

/**
 * Read and parse /proc/loadavg
 * @param metrics Output structure for load average metrics
 * @return 0 on success, -1 on error
 */
int read_proc_loadavg(struct loadavg_metrics *metrics);

/**
 * Print meminfo metrics as JSON to stdout
 * @param metrics Memory metrics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_meminfo_json(const struct meminfo_metrics *metrics, uint64_t timestamp);

/**
 * Print loadavg metrics as JSON to stdout
 * @param metrics Load average metrics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_loadavg_json(const struct loadavg_metrics *metrics, uint64_t timestamp);

#endif // PROC_SCRAPER_H

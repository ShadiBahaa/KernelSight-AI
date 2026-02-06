// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Scraper daemon: periodically polls /proc and /sys for metrics
// Emits JSON events to stdout every 1 second

#include "net_stats.h"
#include "proc_scraper.h"
#include "sysfs_scraper.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>


static volatile sig_atomic_t running = 1;

static void sig_handler(int sig)
{
    (void)sig; // Unused
    running = 0;
}

/**
 * Get current timestamp in nanoseconds since epoch
 */
static uint64_t get_timestamp_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

int main(int argc, char **argv)
{
    struct meminfo_metrics meminfo;
    struct loadavg_metrics loadavg;
    char **block_devices = NULL;
    int block_device_count = 0;
    uint64_t timestamp;

    (void)argc; // Unused
    (void)argv; // Unused

    // Set up signal handlers for graceful shutdown
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    fprintf(stderr, "KernelSight AI - Sysfs/Procfs Scraper Daemon\n");
    fprintf(stderr, "Polling every 1 second. Press Ctrl+C to exit.\n");
    fprintf(stderr, "JSON output will be written to stdout.\n\n");

    while (running) {
        timestamp = get_timestamp_ns();

        // Collect and emit meminfo metrics
        if (read_proc_meminfo(&meminfo) == 0) {
            print_meminfo_json(&meminfo, timestamp);
        } else {
            fprintf(stderr, "WARNING: failed to read meminfo\n");
        }

        // Collect and emit loadavg metrics
        if (read_proc_loadavg(&loadavg) == 0) {
            print_loadavg_json(&loadavg, timestamp);
        } else {
            fprintf(stderr, "WARNING: failed to read loadavg\n");
        }

        // Discover block devices (do this every iteration to catch new devices)
        if (discover_block_devices(&block_devices, &block_device_count) == 0) {
            // Collect and emit block stats for each device
            for (int i = 0; i < block_device_count; i++) {
                struct block_stats stats;
                if (read_block_stats(block_devices[i], &stats) == 0) {
                    print_block_stats_json(block_devices[i], &stats, timestamp);
                }
                // Silently skip devices without stats (e.g., partitions)
            }
            free_block_devices(block_devices, block_device_count);
            block_devices = NULL;
            block_device_count = 0;
        } else {
            fprintf(stderr, "WARNING: failed to discover block devices\n");
        }

        // Collect and emit network interface metrics
        struct interface_stats *interfaces = NULL;
        int interface_count = 0;
        if (read_net_dev(&interfaces, &interface_count) == 0) {
            for (int i = 0; i < interface_count; i++) {
                print_interface_stats_json(&interfaces[i], timestamp);
            }
            free_interface_stats(interfaces, interface_count);
        } else {
            fprintf(stderr, "WARNING: failed to read network interfaces\n");
        }

        // Collect and emit TCP connection stats
        struct tcp_stats tcp_stats;
        if (read_tcp_stats(&tcp_stats) == 0) {
            print_tcp_stats_json(&tcp_stats, timestamp);
        } else {
            fprintf(stderr, "WARNING: failed to read TCP stats\n");
        }

        // Collect and emit TCP retransmit stats
        struct tcp_retransmit_stats retrans_stats;
        if (read_tcp_retransmits(&retrans_stats) == 0) {
            print_tcp_retransmit_json(&retrans_stats, timestamp);
        } else {
            fprintf(stderr, "WARNING: failed to read TCP retransmit stats\n");
        }

        // Sleep for 1 second
        sleep(1);
    }

    fprintf(stderr, "\nShutting down gracefully...\n");

    return 0;
}

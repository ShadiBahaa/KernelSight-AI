// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Procfs scraper implementation

#include "proc_scraper.h"
#include <stdio.h>
#include <string.h>

#define PROC_MEMINFO "/proc/meminfo"
#define PROC_LOADAVG "/proc/loadavg"

int read_proc_meminfo(struct meminfo_metrics *metrics)
{
    FILE *fp;
    char line[256];
    char key[64];
    uint64_t value;

    if (!metrics) {
        return -1;
    }

    // Initialize to zero
    memset(metrics, 0, sizeof(*metrics));

    fp = fopen(PROC_MEMINFO, "r");
    if (!fp) {
        fprintf(stderr, "ERROR: failed to open %s\n", PROC_MEMINFO);
        return -1;
    }

    // Parse each line: "Key: value kB"
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%63s %lu", key, &value) == 2) {
            // Remove trailing colon from key
            size_t len = strlen(key);
            if (len > 0 && key[len - 1] == ':') {
                key[len - 1] = '\0';
            }

            if (strcmp(key, "MemTotal") == 0) {
                metrics->mem_total_kb = value;
            } else if (strcmp(key, "MemFree") == 0) {
                metrics->mem_free_kb = value;
            } else if (strcmp(key, "MemAvailable") == 0) {
                metrics->mem_available_kb = value;
            } else if (strcmp(key, "Buffers") == 0) {
                metrics->buffers_kb = value;
            } else if (strcmp(key, "Cached") == 0) {
                metrics->cached_kb = value;
            } else if (strcmp(key, "SwapTotal") == 0) {
                metrics->swap_total_kb = value;
            } else if (strcmp(key, "SwapFree") == 0) {
                metrics->swap_free_kb = value;
            } else if (strcmp(key, "Active") == 0) {
                metrics->active_kb = value;
            } else if (strcmp(key, "Inactive") == 0) {
                metrics->inactive_kb = value;
            } else if (strcmp(key, "Dirty") == 0) {
                metrics->dirty_kb = value;
            } else if (strcmp(key, "Writeback") == 0) {
                metrics->writeback_kb = value;
            }
        }
    }

    fclose(fp);
    return 0;
}

int read_proc_loadavg(struct loadavg_metrics *metrics)
{
    FILE *fp;
    char line[256];

    if (!metrics) {
        return -1;
    }

    memset(metrics, 0, sizeof(*metrics));

    fp = fopen(PROC_LOADAVG, "r");
    if (!fp) {
        fprintf(stderr, "ERROR: failed to open %s\n", PROC_LOADAVG);
        return -1;
    }

    // Format: "0.52 0.58 0.59 3/602 29369"
    // load1 load5 load15 running/total last_pid
    if (fgets(line, sizeof(line), fp)) {
        int ret = sscanf(line, "%lf %lf %lf %u/%u %u", &metrics->load_1min, &metrics->load_5min,
                         &metrics->load_15min, &metrics->running_processes,
                         &metrics->total_processes, &metrics->last_pid);

        if (ret != 6) {
            fprintf(stderr, "ERROR: failed to parse %s (got %d fields)\n", PROC_LOADAVG, ret);
            fclose(fp);
            return -1;
        }
    } else {
        fprintf(stderr, "ERROR: failed to read %s\n", PROC_LOADAVG);
        fclose(fp);
        return -1;
    }

    fclose(fp);
    return 0;
}

void print_meminfo_json(const struct meminfo_metrics *metrics, uint64_t timestamp)
{
    printf("{\"timestamp\":%lu,\"type\":\"meminfo\",\"data\":{\"mem_total_kb\":%lu,\"mem_free_kb\":"
           "%lu,\"mem_available_kb\":%lu,\"buffers_kb\":%lu,\"cached_kb\":%lu,\"swap_total_kb\":%"
           "lu,\"swap_free_kb\":%lu,\"active_kb\":%lu,\"inactive_kb\":%lu,\"dirty_kb\":%lu,"
           "\"writeback_kb\":%lu}}\n",
           timestamp, metrics->mem_total_kb, metrics->mem_free_kb, metrics->mem_available_kb,
           metrics->buffers_kb, metrics->cached_kb, metrics->swap_total_kb, metrics->swap_free_kb,
           metrics->active_kb, metrics->inactive_kb, metrics->dirty_kb, metrics->writeback_kb);
    fflush(stdout);
}

void print_loadavg_json(const struct loadavg_metrics *metrics, uint64_t timestamp)
{
    printf(
        "{\"timestamp\":%lu,\"type\":\"loadavg\",\"data\":{\"load_1min\":%.2f,\"load_5min\":%.2f,"
        "\"load_15min\":%.2f,\"running_processes\":%u,\"total_processes\":%u,\"last_pid\":%u}}\n",
        timestamp, metrics->load_1min, metrics->load_5min, metrics->load_15min,
        metrics->running_processes, metrics->total_processes, metrics->last_pid);
    fflush(stdout);
}

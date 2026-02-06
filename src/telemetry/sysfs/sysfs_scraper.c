// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Sysfs scraper implementation

#include "sysfs_scraper.h"
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SYS_BLOCK_DIR "/sys/block"

int discover_block_devices(char ***devices, int *count)
{
    DIR *dir;
    struct dirent *entry;
    char **dev_list = NULL;
    int dev_count = 0;
    int capacity = 16;

    if (!devices || !count) {
        return -1;
    }

    dir = opendir(SYS_BLOCK_DIR);
    if (!dir) {
        fprintf(stderr, "ERROR: failed to open %s\n", SYS_BLOCK_DIR);
        return -1;
    }

    // Allocate initial array
    dev_list = malloc(capacity * sizeof(char *));
    if (!dev_list) {
        closedir(dir);
        return -1;
    }

    // Read all entries
    while ((entry = readdir(dir)) != NULL) {
        // Skip . and ..
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }

        // Expand array if needed
        if (dev_count >= capacity) {
            capacity *= 2;
            char **new_list = realloc(dev_list, capacity * sizeof(char *));
            if (!new_list) {
                free_block_devices(dev_list, dev_count);
                closedir(dir);
                return -1;
            }
            dev_list = new_list;
        }

        // Copy device name
        dev_list[dev_count] = strdup(entry->d_name);
        if (!dev_list[dev_count]) {
            free_block_devices(dev_list, dev_count);
            closedir(dir);
            return -1;
        }
        dev_count++;
    }

    closedir(dir);

    *devices = dev_list;
    *count = dev_count;
    return 0;
}

int read_block_stats(const char *device, struct block_stats *stats)
{
    char path[512];
    FILE *fp;

    if (!device || !stats) {
        return -1;
    }

    memset(stats, 0, sizeof(*stats));

    // Build path: /sys/block/[device]/stat
    snprintf(path, sizeof(path), "%s/%s/stat", SYS_BLOCK_DIR, device);

    fp = fopen(path, "r");
    if (!fp) {
        // Not an error - some devices may not have stats (e.g., partitions)
        return -1;
    }

    // Parse the 11 fields from stat file
    int ret =
        fscanf(fp, "%lu %lu %lu %lu %lu %lu %lu %lu %lu %lu %lu", &stats->read_ios,
               &stats->read_merges, &stats->read_sectors, &stats->read_ticks, &stats->write_ios,
               &stats->write_merges, &stats->write_sectors, &stats->write_ticks, &stats->in_flight,
               &stats->io_ticks, &stats->time_in_queue);

    fclose(fp);

    if (ret != 11) {
        fprintf(stderr, "WARNING: failed to parse %s (got %d fields)\n", path, ret);
        return -1;
    }

    return 0;
}

void print_block_stats_json(const char *device, const struct block_stats *stats, uint64_t timestamp)
{
    printf("{\"timestamp\":%lu,\"type\":\"blockstats\",\"device\":\"%s\",\"data\":{\"read_ios\":%"
           "lu,\"read_merges\":%lu,\"read_sectors\":%lu,\"read_ticks_ms\":%lu,\"write_ios\":%lu,"
           "\"write_merges\":%lu,\"write_sectors\":%lu,\"write_ticks_ms\":%lu,\"in_flight\":%lu,"
           "\"io_ticks_ms\":%lu,\"time_in_queue_ms\":%lu}}\n",
           timestamp, device, stats->read_ios, stats->read_merges, stats->read_sectors,
           stats->read_ticks, stats->write_ios, stats->write_merges, stats->write_sectors,
           stats->write_ticks, stats->in_flight, stats->io_ticks, stats->time_in_queue);
    fflush(stdout);
}

void free_block_devices(char **devices, int count)
{
    if (!devices) {
        return;
    }

    for (int i = 0; i < count; i++) {
        free(devices[i]);
    }
    free(devices);
}

// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Userspace loader for I/O latency tracer
// Aggregates histogram data and calculates percentiles

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAX_SLOTS 32

// Histogram structure (must match BPF program)
struct hist {
    unsigned int slots[MAX_SLOTS];
};

// Per-operation statistics (must match BPF program)
struct io_stats {
    struct hist read_hist;
    struct hist write_hist;
    unsigned long long read_count;
    unsigned long long write_count;
    unsigned long long read_bytes;
    unsigned long long write_bytes;
};

static volatile sig_atomic_t exiting = 0;

static void sig_handler(int sig)
{
    exiting = 1;
}

// Calculate percentile from histogram
static double calculate_percentile(const struct hist *h, unsigned long long total,
                                   double percentile)
{
    if (total == 0) {
        return 0.0;
    }

    unsigned long long target = (unsigned long long)(total * percentile / 100.0);
    unsigned long long cumulative = 0;

    for (int i = 0; i < MAX_SLOTS; i++) {
        cumulative += h->slots[i];

        if (cumulative >= target) {
            // Found the bucket containing our percentile
            // Bucket i represents range [2^i, 2^(i+1))
            // Interpolate within the bucket
            unsigned long long bucket_start = (i == 0) ? 0 : (1ULL << i);
            unsigned long long bucket_end = (1ULL << (i + 1));

            // Simple midpoint approximation
            double value = (bucket_start + bucket_end) / 2.0;

            return value;
        }
    }

    // If we get here, return the max value
    return (1ULL << MAX_SLOTS) / 2.0;
}

// Get max latency from histogram
static double get_max_latency(const struct hist *h)
{
    for (int i = MAX_SLOTS - 1; i >= 0; i--) {
        if (h->slots[i] > 0) {
            // Return the upper bound of this bucket
            return (double)(1ULL << (i + 1));
        }
    }
    return 0.0;
}

// Print JSON stats as single line (JSONL format)
static void print_stats(const struct io_stats *stats, unsigned long long timestamp)
{
    struct tm *tm;
    time_t t;
    char ts_str[64];

    t = timestamp / 1000000000;
    tm = localtime(&t);
    strftime(ts_str, sizeof(ts_str), "%Y-%m-%d %H:%M:%S", tm);

    // Calculate percentiles
    double read_p50 = 0, read_p95 = 0, read_p99 = 0, read_max = 0;
    double write_p50 = 0, write_p95 = 0, write_p99 = 0, write_max = 0;

    if (stats->read_count > 0) {
        read_p50 = calculate_percentile(&stats->read_hist, stats->read_count, 50.0);
        read_p95 = calculate_percentile(&stats->read_hist, stats->read_count, 95.0);
        read_p99 = calculate_percentile(&stats->read_hist, stats->read_count, 99.0);
        read_max = get_max_latency(&stats->read_hist);
    }

    if (stats->write_count > 0) {
        write_p50 = calculate_percentile(&stats->write_hist, stats->write_count, 50.0);
        write_p95 = calculate_percentile(&stats->write_hist, stats->write_count, 95.0);
        write_p99 = calculate_percentile(&stats->write_hist, stats->write_count, 99.0);
        write_max = get_max_latency(&stats->write_hist);
    }

    // Output as single-line JSON (JSONL format)
    printf("{\"timestamp\":%llu,\"time_str\":\"%s\",\"interval_seconds\":1,"
           "\"read_count\":%llu,\"read_bytes\":%llu,\"read_p50_us\":%.2f,\"read_p95_us\":%.2f,"
           "\"read_p99_us\":%.2f,\"read_max_us\":%.2f,"
           "\"write_count\":%llu,\"write_bytes\":%llu,\"write_p50_us\":%.2f,\"write_p95_us\":%.2f,"
           "\"write_p99_us\":%.2f,\"write_max_us\":%.2f,"
           "\"type\":\"io\"}\n",
           timestamp, ts_str, stats->read_count, stats->read_bytes, read_p50, read_p95, read_p99,
           read_max, stats->write_count, stats->write_bytes, write_p50, write_p95, write_p99,
           write_max);
    fflush(stdout);
}

// Merge per-CPU stats into a single aggregate
static void merge_stats(int stats_map_fd, struct io_stats *merged)
{
    unsigned int nr_cpus = libbpf_num_possible_cpus();
    struct io_stats *cpu_stats = calloc(nr_cpus, sizeof(struct io_stats));
    if (!cpu_stats) {
        return;
    }

    memset(merged, 0, sizeof(*merged));

    unsigned int key = 0;
    if (bpf_map_lookup_elem(stats_map_fd, &key, cpu_stats) == 0) {
        // Merge all per-CPU stats
        for (unsigned int cpu = 0; cpu < nr_cpus; cpu++) {
            merged->read_count += cpu_stats[cpu].read_count;
            merged->write_count += cpu_stats[cpu].write_count;
            merged->read_bytes += cpu_stats[cpu].read_bytes;
            merged->write_bytes += cpu_stats[cpu].write_bytes;

            // Merge histograms
            for (int i = 0; i < MAX_SLOTS; i++) {
                merged->read_hist.slots[i] += cpu_stats[cpu].read_hist.slots[i];
                merged->write_hist.slots[i] += cpu_stats[cpu].write_hist.slots[i];
            }
        }
    }

    free(cpu_stats);
}

// Clear per-CPU stats
static void clear_stats(int stats_map_fd)
{
    unsigned int nr_cpus = libbpf_num_possible_cpus();
    struct io_stats *zero_stats = calloc(nr_cpus, sizeof(struct io_stats));
    if (!zero_stats) {
        return;
    }

    unsigned int key = 0;
    bpf_map_update_elem(stats_map_fd, &key, zero_stats, BPF_ANY);

    free(zero_stats);
}

static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args)
{
    if (level >= LIBBPF_INFO) {
        return vfprintf(stderr, format, args);
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct bpf_object *obj = NULL;
    struct bpf_program *prog_issue, *prog_complete;
    struct bpf_link *link_issue = NULL, *link_complete = NULL;
    int stats_map_fd = -1;
    int err = 0;

    (void)argc;
    (void)argv;

    // Set up libbpf logging
    libbpf_set_print(libbpf_print_fn);

    // Set up signal handlers
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    fprintf(stderr, "Loading eBPF program...\n");

    // Open BPF object file
    obj = bpf_object__open_file("io_latency_tracer.bpf.o", NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "ERROR: failed to open BPF object file\n");
        return 1;
    }

    // Load BPF object into kernel
    err = bpf_object__load(obj);
    if (err) {
        fprintf(stderr, "ERROR: failed to load BPF object: %d\n", err);
        goto cleanup;
    }

    fprintf(stderr, "BPF program loaded successfully\n");

    // Find BPF programs
    prog_issue = bpf_object__find_program_by_name(obj, "trace_block_rq_issue");
    prog_complete = bpf_object__find_program_by_name(obj, "trace_block_rq_complete");

    if (!prog_issue || !prog_complete) {
        fprintf(stderr, "ERROR: failed to find BPF programs\n");
        err = -1;
        goto cleanup;
    }

    // Attach BPF programs
    link_issue = bpf_program__attach(prog_issue);
    if (libbpf_get_error(link_issue)) {
        fprintf(stderr, "ERROR: failed to attach block_rq_issue tracepoint\n");
        link_issue = NULL;
        err = -1;
        goto cleanup;
    }

    link_complete = bpf_program__attach(prog_complete);
    if (libbpf_get_error(link_complete)) {
        fprintf(stderr, "ERROR: failed to attach block_rq_complete tracepoint\n");
        link_complete = NULL;
        err = -1;
        goto cleanup;
    }

    fprintf(stderr, "BPF programs attached to tracepoints\n");

    // Get stats map file descriptor
    stats_map_fd = bpf_object__find_map_fd_by_name(obj, "io_stats_map");
    if (stats_map_fd < 0) {
        fprintf(stderr, "ERROR: failed to find stats map\n");
        err = stats_map_fd;
        goto cleanup;
    }

    fprintf(stderr, "Tracing block I/O latency... Press Ctrl+C to exit\n\n");

    // Poll and emit stats every second
    while (!exiting) {
        sleep(1);

        unsigned long long timestamp = time(NULL) * 1000000000ULL;

        // Merge per-CPU stats
        struct io_stats merged_stats;
        merge_stats(stats_map_fd, &merged_stats);

        // Print if we have any activity
        if (merged_stats.read_count > 0 || merged_stats.write_count > 0) {
            print_stats(&merged_stats, timestamp);
        }

        // Clear stats for next interval
        clear_stats(stats_map_fd);
    }

    fprintf(stderr, "\nShutting down...\n");

cleanup:
    bpf_link__destroy(link_issue);
    bpf_link__destroy(link_complete);
    bpf_object__close(obj);

    return err != 0;
}

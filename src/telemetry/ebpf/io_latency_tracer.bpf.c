// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Block I/O Latency Tracer
// Captures block I/O requests and measures latency with histogram aggregation

// eBPF program using vmlinux.h from kernel BTF
// Requires: Ubuntu 22.04+ LTS (kernel 5.15+) with BTF support
#include "vmlinux.h"

#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define MAX_SLOTS 32 // Log2 histogram slots (covers 0 to 2^31 microseconds)

// Histogram for latency distribution (log2 buckets)
struct hist {
    __u32 slots[MAX_SLOTS];
};

// Per-operation statistics
struct io_stats {
    struct hist read_hist;
    struct hist write_hist;
    __u64 read_count;
    __u64 write_count;
    __u64 read_bytes;
    __u64 write_bytes;
};

// Composite key for tracking I/O requests
// Use device + sector as unique identifier
struct request_key {
    __u32 dev;
    __u64 sector;
};

// Track I/O request start time
struct io_start {
    __u64 timestamp; // Issue time in nanoseconds
};

// Aggregated stats event sent to userspace
struct io_stats_event {
    __u64 timestamp;
    __u32 interval_seconds;
    struct io_stats stats;
};

// Hash map to track I/O request start times
// Key: (device, sector) composite key, Value: start timestamp
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, struct request_key); // Changed from __u64 to composite key
    __type(value, struct io_start);
} io_start_map SEC(".maps");

// Per-CPU array for statistics (lock-free updates)
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct io_stats);
} io_stats_map SEC(".maps");

// Ring buffer for emitting aggregated events
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} events SEC(".maps");

// Helper: Calculate log2 of a value for histogram bucketing
// Uses manual loop instead of __builtin_clzll to avoid LLVM backend issues
static __always_inline __u32 log2(__u64 v)
{
    __u32 slot = 0;
    __u64 temp = v;

    // Handle edge case
    if (v == 0) {
        return 0;
    }

// Manual bit scan (unrolled for BPF verifier)
#pragma unroll
    for (int i = 5; i >= 0; i--) {
        __u32 shift = (1 << i);
        if (temp >= (1ULL << shift)) {
            slot += shift;
            temp >>= shift;
        }
    }

    if (slot >= MAX_SLOTS) {
        slot = MAX_SLOTS - 1;
    }

    return slot;
}

// Tracepoint context for block_rq_issue
struct trace_event_raw_block_rq_issue {
    __u64 unused;
    __u32 dev;
    __u64 sector;
    __u32 nr_sector;
    __u32 bytes;
    char rwbs[8];
    char comm[16];
    __u64 __data_loc_cmd;
};

// Tracepoint context for block_rq_complete
struct trace_event_raw_block_rq_complete {
    __u64 unused;
    __u32 dev;
    __u64 sector;
    __u32 nr_sector;
    __u32 errors;
    char rwbs[8];
    __u64 __data_loc_cmd;
};

// Tracepoint: block_rq_issue - when request is issued
SEC("tp/block/block_rq_issue")
int trace_block_rq_issue(struct trace_event_raw_block_rq_issue *ctx)
{
    // Use device + sector as unique request identifier
    struct request_key key = {
        .dev = ctx->dev,
        .sector = ctx->sector,
    };

    struct io_start start = {.timestamp = bpf_ktime_get_ns()};

    bpf_map_update_elem(&io_start_map, &key, &start, BPF_ANY);

    return 0;
}

// Tracepoint: block_rq_complete - when request completes
SEC("tp/block/block_rq_complete")
int trace_block_rq_complete(struct trace_event_raw_block_rq_complete *ctx)
{
    // Use device + sector as unique request identifier
    struct request_key key = {
        .dev = ctx->dev,
        .sector = ctx->sector,
    };

    // Lookup start time
    struct io_start *start = bpf_map_lookup_elem(&io_start_map, &key);
    if (!start) {
        return 0; // No start time tracked
    }

    // Calculate latency in nanoseconds
    __u64 end_ts = bpf_ktime_get_ns();
    __u64 latency_ns = end_ts - start->timestamp;

    // Convert to microseconds for histogram
    __u64 latency_us = latency_ns / 1000;

    // Determine if read or write from rwbs string
    // 'R' = read, 'W' = write
    char op = ctx->rwbs[0];
    int is_read = (op == 'R');

    // Get per-CPU stats
    __u32 stats_key = 0;
    struct io_stats *stats = bpf_map_lookup_elem(&io_stats_map, &stats_key);
    if (!stats) {
        goto cleanup;
    }

    // Calculate histogram slot (log2)
    __u32 slot = log2(latency_us);

    // Update histogram and counters
    if (is_read) {
        __sync_fetch_and_add(&stats->read_hist.slots[slot], 1);
        __sync_fetch_and_add(&stats->read_count, 1);
        __sync_fetch_and_add(&stats->read_bytes, ctx->nr_sector * 512);
    } else {
        __sync_fetch_and_add(&stats->write_hist.slots[slot], 1);
        __sync_fetch_and_add(&stats->write_count, 1);
        __sync_fetch_and_add(&stats->write_bytes, ctx->nr_sector * 512);
    }

cleanup:
    // Remove from tracking map
    bpf_map_delete_elem(&io_start_map, &key);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";

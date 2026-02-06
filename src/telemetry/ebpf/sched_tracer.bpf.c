// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Scheduler Events Tracer
// Captures sched_switch and sched_wakeup events, computes per-process
// context switch rates, and aggregates to 1-second buckets

// eBPF program using vmlinux.h from kernel BTF
// Requires: Ubuntu 22.04+ LTS (kernel 5.15+) with BTF support
#include "vmlinux.h"

#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define TASK_COMM_LEN 16
#define NSEC_PER_SEC 1000000000ULL

// Event types
#define EVENT_SCHED_SWITCH 1
#define EVENT_SCHED_WAKEUP 2

// Aggregated statistics per process per 1-second bucket
struct bucket_stats {
    __u64 time_bucket;          // Bucket timestamp (seconds since boot)
    __u32 pid;                  // Process ID
    char comm[TASK_COMM_LEN];   // Process name
    __u64 context_switches;     // Total context switches in bucket
    __u64 voluntary_switches;   // Voluntary context switches
    __u64 involuntary_switches; // Involuntary context switches
    __u64 wakeups;              // Number of times process was woken up
    __u64 cpu_time_ns;          // Total CPU time in bucket (nanoseconds)
    __u64 total_timeslice_ns;   // Sum of all timeslices for avg calculation
    __u32 timeslice_count;      // Number of timeslices for averaging
};

// Composite key for bucket aggregation: (pid, time_bucket)
struct bucket_key {
    __u32 pid;
    __u64 time_bucket;
};

// Per-process tracking of last scheduled timestamp
struct process_state {
    __u64 last_switch_ts;     // Last time process was switched out
    __u64 last_bucket;        // Last bucket we emitted for this process
    char comm[TASK_COMM_LEN]; // Process name
};

// Custom structure for sched_wakeup tracepoint arguments
// Based on kernel tracepoint format: /sys/kernel/debug/tracing/events/sched/sched_wakeup/format
struct sched_wakeup_args {
    __u64 pad;        // Common tracepoint header
    char comm[16];    // Task command name
    __u32 pid;        // Task PID
    __u32 prio;       // Task priority
    __u32 target_cpu; // Target CPU
};

// Hash map for per-process state tracking
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, __u32);
    __type(value, struct process_state);
} process_state_map SEC(".maps");

// Hash map for 1-second bucket aggregates
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, struct bucket_key);
    __type(value, struct bucket_stats);
} bucket_aggregates SEC(".maps");

// Ring buffer for emitting aggregated events
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256KB ring buffer
} events SEC(".maps");

// Helper function to emit bucket stats to userspace
static __always_inline void emit_bucket_stats(struct bucket_key *key, struct bucket_stats *stats)
{
    struct bucket_stats *event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        return;
    }

    // Copy stats to event
    event->time_bucket = stats->time_bucket;
    event->pid = stats->pid;
    __builtin_memcpy(event->comm, stats->comm, TASK_COMM_LEN);
    event->context_switches = stats->context_switches;
    event->voluntary_switches = stats->voluntary_switches;
    event->involuntary_switches = stats->involuntary_switches;
    event->wakeups = stats->wakeups;
    event->cpu_time_ns = stats->cpu_time_ns;
    event->total_timeslice_ns = stats->total_timeslice_ns;
    event->timeslice_count = stats->timeslice_count;

    bpf_ringbuf_submit(event, 0);
}

// Helper function to update or create bucket stats
static __always_inline void update_bucket_stats(__u32 pid, __u64 time_bucket, __u64 cpu_time,
                                                int is_voluntary, int is_wakeup, char *comm)
{
    struct bucket_key key = {.pid = pid, .time_bucket = time_bucket};

    struct bucket_stats *stats = bpf_map_lookup_elem(&bucket_aggregates, &key);
    if (stats) {
        // Update existing bucket
        if (is_wakeup) {
            stats->wakeups++;
        } else {
            stats->context_switches++;
            if (is_voluntary) {
                stats->voluntary_switches++;
            } else {
                stats->involuntary_switches++;
            }
            stats->cpu_time_ns += cpu_time;
            stats->total_timeslice_ns += cpu_time;
            stats->timeslice_count++;
        }
    } else {
        // Create new bucket
        struct bucket_stats new_stats = {.time_bucket = time_bucket,
                                         .pid = pid,
                                         .context_switches = is_wakeup ? 0 : 1,
                                         .voluntary_switches = (is_wakeup || !is_voluntary) ? 0 : 1,
                                         .involuntary_switches =
                                             (is_wakeup || is_voluntary) ? 0 : 1,
                                         .wakeups = is_wakeup ? 1 : 0,
                                         .cpu_time_ns = cpu_time,
                                         .total_timeslice_ns = cpu_time,
                                         .timeslice_count = is_wakeup ? 0 : 1};
        __builtin_memcpy(new_stats.comm, comm, TASK_COMM_LEN);

        bpf_map_update_elem(&bucket_aggregates, &key, &new_stats, BPF_ANY);
    }
}

// Tracepoint for sched_switch
// This captures context switches between processes
SEC("tp/sched/sched_switch")
int trace_sched_switch(struct trace_event_raw_sched_switch *ctx)
{
    __u64 now = bpf_ktime_get_ns();
    __u64 time_bucket = now / NSEC_PER_SEC;

    // Get previous task info (task being switched out)
    __u32 prev_pid = ctx->prev_pid;
    __u32 prev_state = ctx->prev_state;

    // Get next task info (task being switched in)
    __u32 next_pid = ctx->next_pid;

    // Determine if switch is voluntary or involuntary
    // prev_state == 0 (TASK_RUNNING) means involuntary (preempted)
    // prev_state != 0 means voluntary (blocked/sleeping)
    int is_voluntary = (prev_state != 0);

    // Process the outgoing task (prev)
    if (prev_pid > 0) { // Ignore idle process (pid 0)
        struct process_state *state = bpf_map_lookup_elem(&process_state_map, &prev_pid);
        __u64 cpu_time = 0;

        if (state) {
            // Calculate time slice
            if (state->last_switch_ts > 0) {
                cpu_time = now - state->last_switch_ts;
            }

            // Check if we moved to a new bucket, emit old bucket if so
            if (state->last_bucket != 0 && state->last_bucket != time_bucket) {
                struct bucket_key old_key = {.pid = prev_pid, .time_bucket = state->last_bucket};
                struct bucket_stats *old_stats = bpf_map_lookup_elem(&bucket_aggregates, &old_key);
                if (old_stats) {
                    emit_bucket_stats(&old_key, old_stats);
                    bpf_map_delete_elem(&bucket_aggregates, &old_key);
                }
            }

            state->last_bucket = time_bucket;
        } else {
            // First time seeing this process
            struct process_state new_state = {.last_switch_ts = 0, .last_bucket = time_bucket};
            bpf_probe_read_kernel_str(new_state.comm, TASK_COMM_LEN, ctx->prev_comm);
            bpf_map_update_elem(&process_state_map, &prev_pid, &new_state, BPF_ANY);
        }

        // Update bucket stats for previous process
        char prev_comm[TASK_COMM_LEN];
        bpf_probe_read_kernel_str(prev_comm, TASK_COMM_LEN, ctx->prev_comm);
        update_bucket_stats(prev_pid, time_bucket, cpu_time, is_voluntary, 0, prev_comm);
    }

    // Track incoming task (next) - update its last_switch_ts
    if (next_pid > 0) {
        struct process_state *next_state = bpf_map_lookup_elem(&process_state_map, &next_pid);
        if (next_state) {
            next_state->last_switch_ts = now;
        } else {
            struct process_state new_state = {.last_switch_ts = now, .last_bucket = time_bucket};
            bpf_probe_read_kernel_str(new_state.comm, TASK_COMM_LEN, ctx->next_comm);
            bpf_map_update_elem(&process_state_map, &next_pid, &new_state, BPF_ANY);
        }
    }

    return 0;
}

// Tracepoint for sched_wakeup
// This captures when a process becomes runnable
SEC("tp/sched/sched_wakeup")
int trace_sched_wakeup(struct sched_wakeup_args *ctx)
{
    __u64 now = bpf_ktime_get_ns();
    __u64 time_bucket = now / NSEC_PER_SEC;

    // Access fields directly from our custom structure
    __u32 pid = ctx->pid;

    if (pid == 0) {
        return 0; // Ignore idle process
    }

    // comm is already in the structure, just read it
    char comm[TASK_COMM_LEN];
    __builtin_memcpy(comm, ctx->comm, TASK_COMM_LEN);

    // Update bucket stats for wakeup
    update_bucket_stats(pid, time_bucket, 0, 0, 1, comm);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";

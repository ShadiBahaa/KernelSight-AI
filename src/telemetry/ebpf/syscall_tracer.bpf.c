// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// High-Latency Syscall Tracer
// Captures system calls with latency >10ms for performance analysis

// eBPF program using vmlinux.h from kernel BTF
// Requires: Ubuntu 22.04+ LTS (kernel 5.15+) with BTF support
#include "vmlinux.h"

#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define TASK_COMM_LEN 16
#define LATENCY_THRESHOLD_NS 10000000ULL // 10ms in nanoseconds

// Event structure sent to userspace
struct syscall_event {
    __u64 timestamp;          // Event timestamp (nanoseconds)
    __u32 pid;                // Process ID
    __u32 tid;                // Thread ID
    __u32 syscall_nr;         // Syscall number
    __u64 latency_ns;         // Syscall latency in nanoseconds
    __s64 ret_value;          // Syscall return value
    __u64 arg0;               // First argument (useful for identifying files, fds, etc.)
    __u32 cpu;                // CPU core where syscall executed
    __u32 uid;                // User ID of the process
    __u8 is_error;            // 1 if return value indicates error (<0)
    char comm[TASK_COMM_LEN]; // Process name
};

// Structure to store syscall entry data
struct syscall_entry_data {
    __u64 timestamp; // Entry timestamp
    __u64 arg0;      // First syscall argument
};

// Hash map to store syscall entry data
// Key: thread ID, Value: entry data (timestamp + arg0)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 8192);
    __type(key, __u32);
    __type(value, struct syscall_entry_data);
} syscall_start SEC(".maps");

// Ring buffer for sending events to userspace
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256KB ring buffer
} events SEC(".maps");

// Tracepoint for syscall entry
SEC("tracepoint/raw_syscalls/sys_enter")
int trace_syscall_enter(struct trace_event_raw_sys_enter *ctx)
{
    __u64 tid = bpf_get_current_pid_tgid();
    __u32 tid_key = (__u32)tid;

    // Capture entry data: timestamp and first argument
    struct syscall_entry_data entry_data = {
        .timestamp = bpf_ktime_get_ns(),
        .arg0 = ctx->args[0] // First syscall argument
    };

    // Store entry data for this thread
    bpf_map_update_elem(&syscall_start, &tid_key, &entry_data, BPF_ANY);

    return 0;
}

// Tracepoint for syscall exit
SEC("tracepoint/raw_syscalls/sys_exit")
int trace_syscall_exit(struct trace_event_raw_sys_exit *ctx)
{
    __u64 tid_pid = bpf_get_current_pid_tgid();
    __u32 tid = (__u32)tid_pid;
    __u32 pid = tid_pid >> 32;

    // Lookup entry data (timestamp + arg0)
    struct syscall_entry_data *entry_data = bpf_map_lookup_elem(&syscall_start, &tid);
    if (!entry_data) {
        return 0; // No entry tracked for this thread
    }

    __u64 end_ts = bpf_ktime_get_ns();
    __u64 latency = end_ts - entry_data->timestamp;

    // Filter: only emit events for high-latency syscalls (>10ms)
    if (latency < LATENCY_THRESHOLD_NS) {
        bpf_map_delete_elem(&syscall_start, &tid);
        return 0;
    }

    // Reserve space in ring buffer
    struct syscall_event *event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        bpf_map_delete_elem(&syscall_start, &tid);
        return 0;
    }

    // Populate event data
    event->timestamp = end_ts;
    event->pid = pid;
    event->tid = tid;
    event->syscall_nr = ctx->id;
    event->latency_ns = latency;
    event->ret_value = ctx->ret;
    event->is_error = (ctx->ret < 0) ? 1 : 0;
    event->cpu = bpf_get_smp_processor_id();
    event->uid = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    event->arg0 = entry_data->arg0; // First syscall argument from entry
    bpf_get_current_comm(&event->comm, sizeof(event->comm));

    // Submit event to userspace
    bpf_ringbuf_submit(event, 0);

    // Clean up entry from map
    bpf_map_delete_elem(&syscall_start, &tid);

    return 0;
}

char LICENSE[] SEC("license") = "GPL";

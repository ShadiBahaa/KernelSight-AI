// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Userspace loader for scheduler events tracer
// Uses libbpf to load eBPF program and output aggregated events as JSON

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define TASK_COMM_LEN 16

// Event structure (must match BPF program)
struct bucket_stats {
    unsigned long long time_bucket;
    unsigned int pid;
    char comm[TASK_COMM_LEN];
    unsigned long long context_switches;
    unsigned long long voluntary_switches;
    unsigned long long involuntary_switches;
    unsigned long long wakeups;
    unsigned long long cpu_time_ns;
    unsigned long long total_timeslice_ns;
    unsigned int timeslice_count;
};

static volatile sig_atomic_t exiting = 0;

static void sig_handler(int sig)
{
    exiting = 1;
}

// Callback function for ring buffer events
static int handle_event(void *ctx, void *data, size_t data_sz)
{
    const struct bucket_stats *e = data;
    double cpu_time_ms;
    double avg_timeslice_us;

    if (data_sz < sizeof(*e)) {
        fprintf(stderr, "Error: event too small\n");
        return 0;
    }

    // Convert CPU time to milliseconds
    cpu_time_ms = e->cpu_time_ns / 1000000.0;

    // Calculate average timeslice in microseconds
    avg_timeslice_us = 0.0;
    if (e->timeslice_count > 0) {
        avg_timeslice_us = (e->total_timeslice_ns / (double)e->timeslice_count) / 1000.0;
    }

    // Output as single-line JSON (JSONL format for streaming)
    printf("{\"time_bucket\":%llu,\"pid\":%u,\"comm\":\"%s\",\"context_switches\":%llu,\"voluntary_"
           "switches\":%llu,\"involuntary_switches\":%llu,\"wakeups\":%llu,\"cpu_time_ms\":%.3f,"
           "\"avg_timeslice_us\":%.3f,\"type\":\"sched\"}\n",
           e->time_bucket, e->pid, e->comm, e->context_switches, e->voluntary_switches,
           e->involuntary_switches, e->wakeups, cpu_time_ms, avg_timeslice_us);
    fflush(stdout);

    return 0;
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
    struct bpf_program *prog_switch, *prog_wakeup;
    struct bpf_link *link_switch = NULL, *link_wakeup = NULL;
    struct ring_buffer *rb = NULL;
    int err = 0;
    int map_fd;

    // Set up libbpf logging
    libbpf_set_print(libbpf_print_fn);

    // Set up signal handlers
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    fprintf(stderr, "Loading eBPF scheduler tracer...\n");

    // Open BPF object file
    obj = bpf_object__open_file("sched_tracer.bpf.o", NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "ERROR: failed to open BPF object file\n");
        fprintf(stderr, "Make sure sched_tracer.bpf.o exists and is compiled correctly\n");
        return 1;
    }

    // Load BPF object into kernel
    err = bpf_object__load(obj);
    if (err) {
        fprintf(stderr, "ERROR: failed to load BPF object: %d\n", err);
        fprintf(stderr, "Check: 1) Running as root, 2) Kernel has BPF support, 3) BTF enabled\n");
        goto cleanup;
    }

    fprintf(stderr, "BPF program loaded successfully\n");

    // Find BPF programs
    prog_switch = bpf_object__find_program_by_name(obj, "trace_sched_switch");
    prog_wakeup = bpf_object__find_program_by_name(obj, "trace_sched_wakeup");

    if (!prog_switch || !prog_wakeup) {
        fprintf(stderr, "ERROR: failed to find BPF programs\n");
        fprintf(stderr, "Expected programs: trace_sched_switch, trace_sched_wakeup\n");
        err = -1;
        goto cleanup;
    }

    // Attach BPF programs to tracepoints
    link_switch = bpf_program__attach(prog_switch);
    if (libbpf_get_error(link_switch)) {
        fprintf(stderr, "ERROR: failed to attach sched_switch tracepoint\n");
        link_switch = NULL;
        err = -1;
        goto cleanup;
    }

    link_wakeup = bpf_program__attach(prog_wakeup);
    if (libbpf_get_error(link_wakeup)) {
        fprintf(stderr, "ERROR: failed to attach sched_wakeup tracepoint\n");
        link_wakeup = NULL;
        err = -1;
        goto cleanup;
    }

    fprintf(stderr, "BPF programs attached to tracepoints\n");

    // Get ring buffer map file descriptor
    map_fd = bpf_object__find_map_fd_by_name(obj, "events");
    if (map_fd < 0) {
        fprintf(stderr, "ERROR: failed to find ring buffer map\n");
        err = map_fd;
        goto cleanup;
    }

    // Set up ring buffer consumer
    rb = ring_buffer__new(map_fd, handle_event, NULL, NULL);
    if (!rb) {
        fprintf(stderr, "ERROR: failed to create ring buffer\n");
        err = -1;
        goto cleanup;
    }

    fprintf(stderr, "Tracing scheduler events (1-second buckets)... Press Ctrl+C to exit\n\n");

    // Poll ring buffer for events
    while (!exiting) {
        err = ring_buffer__poll(rb, 100 /* timeout, ms */);
        if (err == -EINTR) {
            err = 0;
            break;
        }
        if (err < 0) {
            fprintf(stderr, "ERROR: ring buffer polling failed: %d\n", err);
            break;
        }
    }

    fprintf(stderr, "\nShutting down...\n");

cleanup:
    ring_buffer__free(rb);
    bpf_link__destroy(link_switch);
    bpf_link__destroy(link_wakeup);
    bpf_object__close(obj);

    return err != 0;
}

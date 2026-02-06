// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Userspace loader for high-latency syscall tracer
// Uses libbpf to load eBPF program and output events as JSON

// Include generated syscall names - build will fail if not generated
#include "../common/syscall_names.h"
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

// Event structure (must match BPF program)
struct syscall_event {
    unsigned long long timestamp;
    unsigned int pid;
    unsigned int tid;
    unsigned int syscall_nr;
    unsigned long long latency_ns;
    long long ret_value;
    unsigned long long arg0;
    unsigned int cpu;
    unsigned int uid;
    unsigned char is_error;
    char comm[16];
};

static volatile sig_atomic_t exiting = 0;

static void sig_handler(int sig)
{
    exiting = 1;
}

// Callback function for ring buffer events
static int handle_event(void *ctx, void *data, size_t data_sz)
{
    const struct syscall_event *e = data;
    struct tm *tm;
    time_t t;
    char ts_str[64];
    double latency_ms;

    if (data_sz < sizeof(*e)) {
        fprintf(stderr, "Error: event too small\n");
        return 0;
    }

    // Convert timestamp to human-readable format
    t = e->timestamp / 1000000000;
    tm = localtime(&t);
    strftime(ts_str, sizeof(ts_str), "%Y-%m-%d %H:%M:%S", tm);

    // Convert latency to milliseconds
    latency_ms = e->latency_ns / 1000000.0;

    // Output as single-line JSON for pipeline compatibility
    printf("{\"timestamp\":%llu,\"time_str\":\"%s\",\"pid\":%u,\"tid\":%u,\"cpu\":%u,\"uid\":%u,\"syscall\":%u,\"syscall_name\":\"%s\",\"latency_ms\":%.3f,\"ret_value\":%lld,\"is_error\":%s,\"arg0\":%llu,\"comm\":\"%s\"}\n",
        e->timestamp,
        ts_str,
        e->pid,
        e->tid,
        e->cpu,
        e->uid,
        e->syscall_nr,
        get_syscall_name(e->syscall_nr),
        latency_ms,
        e->ret_value,
        e->is_error ? "true" : "false",
        e->arg0,
        e->comm);
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
    struct bpf_program *prog_enter, *prog_exit;
    struct bpf_link *link_enter = NULL, *link_exit = NULL;
    struct ring_buffer *rb = NULL;
    int err = 0;
    int map_fd;

    // Set up libbpf logging
    libbpf_set_print(libbpf_print_fn);

    // Set up signal handlers
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    fprintf(stderr, "Loading eBPF program...\n");

    // Open BPF object file
    obj = bpf_object__open_file("syscall_tracer.bpf.o", NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "ERROR: failed to open BPF object file\n");
        fprintf(stderr, "Make sure syscall_tracer.bpf.o exists and is compiled correctly\n");
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
    prog_enter = bpf_object__find_program_by_name(obj, "trace_syscall_enter");
    prog_exit = bpf_object__find_program_by_name(obj, "trace_syscall_exit");

    if (!prog_enter || !prog_exit) {
        fprintf(stderr, "ERROR: failed to find BPF programs\n");
        err = -1;
        goto cleanup;
    }

    // Attach BPF programs to tracepoints
    link_enter = bpf_program__attach(prog_enter);
    if (libbpf_get_error(link_enter)) {
        fprintf(stderr, "ERROR: failed to attach sys_enter tracepoint\n");
        link_enter = NULL;
        err = -1;
        goto cleanup;
    }

    link_exit = bpf_program__attach(prog_exit);
    if (libbpf_get_error(link_exit)) {
        fprintf(stderr, "ERROR: failed to attach sys_exit tracepoint\n");
        link_exit = NULL;
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

    fprintf(stderr, "Tracing syscalls with latency >10ms... Press Ctrl+C to exit\n\n");

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
    bpf_link__destroy(link_enter);
    bpf_link__destroy(link_exit);
    bpf_object__close(obj);

    return err != 0;
}

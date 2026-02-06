// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Userspace loader for page fault tracer
// Uses libbpf to load eBPF program and output events as JSON

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
struct page_fault_event {
    unsigned long long timestamp;
    unsigned int pid;
    unsigned int tid;
    unsigned long long address;
    unsigned long long latency_ns;
    unsigned int cpu;
    unsigned char is_major;
    unsigned char is_write;
    unsigned char is_kernel;
    unsigned char is_instruction;
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
    const struct page_fault_event *e = data;
    struct tm *tm;
    time_t t;
    char ts_str[64];
    double latency_us;

    if (data_sz < sizeof(*e)) {
        fprintf(stderr, "Error: event too small\n");
        return 0;
    }

    // Convert timestamp to human-readable format
    t = e->timestamp / 1000000000;
    tm = localtime(&t);
    strftime(ts_str, sizeof(ts_str), "%Y-%m-%d %H:%M:%S", tm);

    // Convert latency to microseconds
    latency_us = e->latency_ns / 1000.0;

    // Output as single-line JSON (JSONL format for streaming)
    printf("{\"timestamp\":%llu,\"time_str\":\"%s\",\"pid\":%u,\"tid\":%u,\"comm\":\"%s\","
           "\"address\":\"0x%llx\",\"latency_ns\":%llu,\"latency_us\":%.3f,\"cpu\":%u,\"is_major\":"
           "%s,\"is_write\":%s,\"is_kernel\":%s,\"is_instruction\":%s,\"type\":\"pagefault\"}\n",
           e->timestamp, ts_str, e->pid, e->tid, e->comm, e->address, e->latency_ns, latency_us,
           e->cpu, e->is_major ? "true" : "false", e->is_write ? "true" : "false",
           e->is_kernel ? "true" : "false", e->is_instruction ? "true" : "false");
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
    struct bpf_program *prog_entry, *prog_exit;
    struct bpf_link *link_entry = NULL, *link_exit = NULL;
    struct ring_buffer *rb = NULL;
    int err = 0;
    int map_fd;

    (void)argc; // Unused
    (void)argv; // Unused

    // Set up libbpf logging
    libbpf_set_print(libbpf_print_fn);

    // Set up signal handlers
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    fprintf(stderr, "Loading eBPF program...\n");

    // Open BPF object file
    obj = bpf_object__open_file("page_fault_tracer.bpf.o", NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "ERROR: failed to open BPF object file\n");
        fprintf(stderr, "Make sure page_fault_tracer.bpf.o exists and is compiled correctly\n");
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

    // Find BPF kprobe/kretprobe programs
    prog_entry = bpf_object__find_program_by_name(obj, "trace_mm_fault_entry");
    prog_exit = bpf_object__find_program_by_name(obj, "trace_mm_fault_exit");

    if (!prog_entry || !prog_exit) {
        fprintf(stderr, "ERROR: failed to find BPF programs\n");
        fprintf(stderr,
                "Expected: trace_mm_fault_entry (kprobe), trace_mm_fault_exit (kretprobe)\n");
        err = -1;
        goto cleanup;
    }

    // Attach kprobe on handle_mm_fault entry
    link_entry = bpf_program__attach(prog_entry);
    if (libbpf_get_error(link_entry)) {
        fprintf(stderr, "ERROR: failed to attach kprobe to handle_mm_fault\n");
        fprintf(stderr, "Make sure kernel has kprobe support and handle_mm_fault symbol exists\n");
        link_entry = NULL;
        err = -1;
        goto cleanup;
    }

    // Attach kretprobe on handle_mm_fault exit
    link_exit = bpf_program__attach(prog_exit);
    if (libbpf_get_error(link_exit)) {
        fprintf(stderr, "ERROR: failed to attach kretprobe to handle_mm_fault\n");
        link_exit = NULL;
        err = -1;
        goto cleanup;
    }

    fprintf(stderr, "BPF kprobe/kretprobe attached to handle_mm_fault\n");

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

    fprintf(stderr, "Tracing page faults... Press Ctrl+C to exit\n\n");

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
    bpf_link__destroy(link_entry);
    bpf_link__destroy(link_exit);
    bpf_object__close(obj);

    return err != 0;
}

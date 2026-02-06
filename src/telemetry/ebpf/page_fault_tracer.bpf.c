// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Page Fault Tracer
// Captures page fault events and measures fault handling latency
// Uses kprobe/kretprobe on handle_mm_fault() for full metrics

// eBPF program using vmlinux.h from kernel BTF
// Requires: Ubuntu 22.04+ LTS (kernel 5.15+) with BTF support
// Architecture is defined via CMake: -D__TARGET_ARCH_x86
#include "vmlinux.h"

#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#define TASK_COMM_LEN 16

// VM fault return flags (from include/linux/mm.h)
#define VM_FAULT_OOM 0x0001
#define VM_FAULT_SIGBUS 0x0002
#define VM_FAULT_MAJOR 0x0004 // Major fault (disk I/O required)
#define VM_FAULT_WRITE 0x0008
#define VM_FAULT_HWPOISON 0x0010
#define VM_FAULT_HWPOISON_LARGE 0x0020
#define VM_FAULT_SIGSEGV 0x0040

// Event structure sent to userspace
struct page_fault_event {
    __u64 timestamp;          // Event timestamp (nanoseconds)
    __u32 pid;                // Process ID
    __u32 tid;                // Thread ID
    __u64 address;            // Faulting virtual address
    __u64 latency_ns;         // Fault handling time (nanoseconds)
    __u32 cpu;                // CPU core
    __u8 is_major;            // 1 if major fault (disk I/O required)
    __u8 is_write;            // 1 if write fault
    __u8 is_kernel;           // 1 if kernel-mode fault
    __u8 is_instruction;      // 1 if instruction fetch fault
    char comm[TASK_COMM_LEN]; // Process name
};

// Structure to track page fault entry
struct fault_entry {
    __u64 timestamp;          // Entry timestamp
    __u64 address;            // Faulting address
    __u32 pid;                // Process ID
    __u32 tid;                // Thread ID
    __u32 cpu;                // CPU core
    __u8 is_write;            // Write fault flag
    __u8 is_kernel;           // Kernel-mode fault flag
    char comm[TASK_COMM_LEN]; // Process name
};

// Hash map to track fault entry timestamps
// Key: thread ID, Value: fault entry data
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 8192);
    __type(key, __u32);
    __type(value, struct fault_entry);
} fault_start SEC(".maps");

// Ring buffer for sending events to userspace
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256KB ring buffer
} events SEC(".maps");

// Kprobe entry handler for handle_mm_fault()
// Function signature: vm_fault_t handle_mm_fault(struct vm_area_struct *vma,
//                                                 unsigned long address,
//                                                 unsigned int flags,
//                                                 struct pt_regs *regs)
SEC("kprobe/handle_mm_fault")
int BPF_KPROBE(trace_mm_fault_entry, struct vm_area_struct *vma, unsigned long address,
               unsigned int flags, struct pt_regs *regs)
{
    __u64 tid_pid = bpf_get_current_pid_tgid();
    __u32 tid = (__u32)tid_pid;
    __u32 pid = tid_pid >> 32;

    // Store entry information for latency calculation
    struct fault_entry entry = {};
    entry.timestamp = bpf_ktime_get_ns();
    entry.address = address;
    entry.pid = pid;
    entry.tid = tid;
    entry.cpu = bpf_get_smp_processor_id();

    // Decode fault flags (FAULT_FLAG_* from include/linux/mm.h)
    // FAULT_FLAG_WRITE = 0x01, FAULT_FLAG_USER = 0x04
    entry.is_write = (flags & 0x01) ? 1 : 0;
    entry.is_kernel = (flags & 0x04) ? 0 : 1; // If USER flag not set, it's kernel

    bpf_get_current_comm(&entry.comm, sizeof(entry.comm));

    // Store entry data for retrieval in kretprobe
    bpf_map_update_elem(&fault_start, &tid, &entry, BPF_ANY);

    return 0;
}

// Kretprobe exit handler for handle_mm_fault()
// Captures the return value to determine if major fault occurred
SEC("kretprobe/handle_mm_fault")
int BPF_KRETPROBE(trace_mm_fault_exit, vm_fault_t retval)
{
    __u64 tid_pid = bpf_get_current_pid_tgid();
    __u32 tid = (__u32)tid_pid;

    // Lookup entry data
    struct fault_entry *entry = bpf_map_lookup_elem(&fault_start, &tid);
    if (!entry) {
        return 0; // Missing entry, skip
    }

    // Calculate latency
    __u64 now = bpf_ktime_get_ns();
    __u64 latency_ns = now - entry->timestamp;

    // Reserve space in ring buffer
    struct page_fault_event *event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        goto cleanup;
    }

    // Populate event data
    event->timestamp = entry->timestamp;
    event->pid = entry->pid;
    event->tid = entry->tid;
    event->address = entry->address;
    event->latency_ns = latency_ns;
    event->cpu = entry->cpu;
    event->is_major = (retval & VM_FAULT_MAJOR) ? 1 : 0;
    event->is_write = entry->is_write;
    event->is_kernel = entry->is_kernel;
    event->is_instruction = 0; // Not available from handle_mm_fault context
    __builtin_memcpy(event->comm, entry->comm, TASK_COMM_LEN);

    // Submit event to userspace
    bpf_ringbuf_submit(event, 0);

cleanup:
    // Clean up entry from map
    bpf_map_delete_elem(&fault_start, &tid);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";

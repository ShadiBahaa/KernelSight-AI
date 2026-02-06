# ADR-001: eBPF for Telemetry Collection

## Context

KernelSight AI requires low-overhead collection of kernel-level metrics including scheduler events, memory operations, I/O latency, and network statistics. We need to choose a technology that provides:

1. **Low overhead**: < 1% CPU impact
2. **Safety**: Cannot crash the kernel
3. **Flexibility**: Programmable collection logic
4. **Real-time data**: Event-driven, not just polling

## Decision

We will use eBPF (Extended Berkeley Packet Filter) as the primary technology for kernel telemetry collection.

## Rationale

### Advantages of eBPF

1. **Verified Safety**: eBPF programs are verified by the kernel verifier before loading, preventing crashes
2. **Performance**: In-kernel execution with JIT compilation provides minimal overhead
3. **Flexibility**: Can attach to tracepoints, kprobes, uprobes, and other hook points
4. **Event-Driven**: Real-time collection without polling overhead
5. **Standardization**: Widely adopted in production systems (Cilium, Falco, etc.)

### Alternatives Considered

1. **SystemTap**: Requires kernel modules, higher overhead, less safe
2. **Pure procfs polling**: Cannot capture event-level granularity, higher latency
3. **Kernel modules**: Unsafe, difficult to maintain across kernel versions
4. **ftrace**: Limited programmability compared to eBPF

### Technology Specifics

- **Library**: libbpf for stable API surface
- **Language**: BPF C for performance-critical paths
- **Fallbacks**: Procfs/sysfs polling when eBPF features unavailable

## Consequences

### Positive

- Industry-standard approach with strong community support
- Future-proof as eBPF capabilities expand
- Enables sophisticated filtering and aggregation in-kernel

### Negative

- Requires kernel 5.15+ for advanced features
- Learning curve for eBPF programming
- Debugging eBPF programs can be challenging

### Mitigation

- Provide fallback collectors for older kernels
- Comprehensive documentation and examples
- Use bpftrace for prototyping before implementing in C

## Implementation Notes

- Use BPF ring buffers (kernel 5.8+) for efficient data transfer
- Implement per-CPU data structures to avoid contention
- Keep programs simple to pass verifier constraints
- Use CO-RE (Compile Once, Run Everywhere) for portability

## References

- [eBPF Documentation](https://ebpf.io/)
- [libbpf Documentation](https://github.com/libbpf/libbpf)
- [BPF Performance Tools (Brendan Gregg)](http://www.brendangregg.com/bpf-performance-tools-book.html)

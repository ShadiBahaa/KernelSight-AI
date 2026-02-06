# Telemetry Collection Build Configuration

# ============================================================================
# Dependency Checking (Ubuntu 22.04+ LTS Focus)
# ============================================================================

# Required: Clang for BPF compilation
find_program(CLANG clang)
find_program(LLVM_STRIP llvm-strip)
find_program(AUSYSCALL ausyscall)

# Check for libbpf (pkg-config)
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(LIBBPF libbpf)
endif()

# Dependency validation with helpful error messages
if(BUILD_EBPF)
    set(MISSING_DEPS "")
    
    if(NOT CLANG)
        list(APPEND MISSING_DEPS "clang")
    endif()
    
    if(NOT LIBBPF_FOUND)
        list(APPEND MISSING_DEPS "libbpf-dev")
   endif()
    
    if(NOT AUSYSCALL)
        list(APPEND MISSING_DEPS "auditd")
    endif()
    
    if(MISSING_DEPS)
        message(FATAL_ERROR 
            "Missing required dependencies for eBPF build: ${MISSING_DEPS}\n"
            "Please install them on Ubuntu 22.04+:\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install -y clang llvm libbpf-dev auditd linux-headers-$(uname -r)\n"
            "\nOr disable eBPF build with: cmake -DBUILD_EBPF=OFF .."
        )
    endif()
    
    message(STATUS "All eBPF dependencies found")
endif()

# ============================================================================
# VMLinux.h Generation (Required for Ubuntu 22.04+ LTS)
# ============================================================================

find_program(BPFTOOL bpftool)

if(BUILD_EBPF)
    # BTF is mandatory - we target Ubuntu 22.04+ LTS exclusively
    if(NOT BPFTOOL)
        message(FATAL_ERROR
            "bpftool not found - required for eBPF build on Ubuntu 22.04+ LTS\n"
            "Install with: sudo apt-get install -y linux-tools-common linux-tools-$(uname -r)"
        )
    endif()
    
    if(NOT EXISTS /sys/kernel/btf/vmlinux)
        message(FATAL_ERROR
            "BTF not available at /sys/kernel/btf/vmlinux\n"
            "This project requires Ubuntu 22.04+ LTS (kernel 5.15+) with BTF support.\n"
            "If running on WSL2, ensure you're using a recent WSL2 kernel."
        )
    endif()
    
    set(VMLINUX_H ${CMAKE_CURRENT_BINARY_DIR}/vmlinux.h)
    
    # Generate vmlinux.h from kernel BTF
    add_custom_command(
        OUTPUT ${VMLINUX_H}
        COMMAND ${BPFTOOL} btf dump file /sys/kernel/btf/vmlinux format c > ${VMLINUX_H}
        COMMENT "Generating vmlinux.h from kernel BTF"
        VERBATIM
    )
    
    add_custom_target(generate_vmlinux_h DEPENDS ${VMLINUX_H})
    message(STATUS "✓ BTF support detected - will generate vmlinux.h")
endif()

# ============================================================================
# Syscall Name Generation
# ============================================================================

if(BUILD_EBPF)
    # Generate syscall names at build time (required)
    set(SYSCALL_NAMES_GEN_SCRIPT ${CMAKE_SOURCE_DIR}/scripts/generate_syscall_names.sh)
    set(SYSCALL_NAMES_HEADER ${CMAKE_CURRENT_SOURCE_DIR}/common/syscall_names.h)
    
    add_custom_command(
        OUTPUT ${SYSCALL_NAMES_HEADER}
        COMMAND bash ${SYSCALL_NAMES_GEN_SCRIPT} ${SYSCALL_NAMES_HEADER}
        DEPENDS ${SYSCALL_NAMES_GEN_SCRIPT}
        COMMENT "Generating syscall name mappings from ausyscall"
        VERBATIM
    )
    
    add_custom_target(generate_syscall_names DEPENDS ${SYSCALL_NAMES_HEADER})
    
    message(STATUS "Will generate syscall names from ausyscall at build time")
endif()

# ============================================================================
# eBPF Programs
# ============================================================================

if(BUILD_EBPF)
    set(BPF_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/syscall_tracer.bpf.c)
    set(BPF_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/syscall_tracer.bpf.o)
    
    # Prepare BPF compilation flags (BTF always used on Ubuntu 22.04+)
    set(BPF_CFLAGS -g -O2 -target bpf -D__TARGET_ARCH_x86)
    
    # Prepare dependencies (vmlinux.h always required)
    set(BPF_DEPENDS ${BPF_SOURCE} ${VMLINUX_H})
    
    # Compile BPF program to object file
    add_custom_command(
        OUTPUT ${BPF_OBJECT}
        COMMAND ${CLANG}
            ${BPF_CFLAGS}
            -I${CMAKE_SOURCE_DIR}/src
            -I${CMAKE_CURRENT_BINARY_DIR}
            -c ${BPF_SOURCE}
            -o ${BPF_OBJECT}
        DEPENDS ${BPF_DEPENDS}
        COMMENT "Compiling BPF program: ${BPF_OBJECT}"
        VERBATIM
    )
    
    # BPF object build target
    add_custom_target(syscall_tracer_bpf ALL DEPENDS ${BPF_OBJECT})
    
    # Strip debug info if available (reduces size) - run after target is built
    if(LLVM_STRIP)
        add_custom_command(
            TARGET syscall_tracer_bpf POST_BUILD
            COMMAND ${LLVM_STRIP} -g ${BPF_OBJECT}
            COMMENT "Stripping BPF debug symbols"
        )
    endif()
    
    # ========================================================================
    # Userspace Loader
    # ========================================================================
    
    add_executable(syscall_tracer
        ebpf/syscall_tracer.c
    )
    
    # Link with libbpf and dependencies
    target_link_libraries(syscall_tracer
        bpf
        elf
        z
    )
    
    
    # Ensure syscall names are generated before building
    add_dependencies(syscall_tracer generate_syscall_names)
    
    # Ensure BPF object is built first
    add_dependencies(syscall_tracer syscall_tracer_bpf)
    
    # Installation
    install(TARGETS syscall_tracer DESTINATION bin)
    install(FILES ${BPF_OBJECT} DESTINATION bin)
    
    message(STATUS "✓ eBPF syscall tracer will be built")
    
    # ========================================================================
    # Scheduler Tracer (Day 3)
    # ========================================================================
    
    set(SCHED_BPF_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/sched_tracer.bpf.c)
    set(SCHED_BPF_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/sched_tracer.bpf.o)
    
    # Prepare dependencies for scheduler tracer (vmlinux.h always required)
    set(SCHED_BPF_DEPENDS ${SCHED_BPF_SOURCE} ${VMLINUX_H})
    
    # Compile scheduler BPF program
    add_custom_command(
        OUTPUT ${SCHED_BPF_OBJECT}
        COMMAND ${CLANG}
            ${BPF_CFLAGS}
            -I${CMAKE_SOURCE_DIR}/src
            -I${CMAKE_CURRENT_BINARY_DIR}
            -c ${SCHED_BPF_SOURCE}
            -o ${SCHED_BPF_OBJECT}
        DEPENDS ${SCHED_BPF_DEPENDS}
        COMMENT "Compiling BPF program: ${SCHED_BPF_OBJECT}"
        VERBATIM
    )
    
    # Scheduler BPF object build target
    add_custom_target(sched_tracer_bpf ALL DEPENDS ${SCHED_BPF_OBJECT})
    
    # Strip debug info if available
    if(LLVM_STRIP)
        add_custom_command(
            TARGET sched_tracer_bpf POST_BUILD
            COMMAND ${LLVM_STRIP} -g ${SCHED_BPF_OBJECT}
            COMMENT "Stripping BPF debug symbols"
        )
    endif()
    
    # Scheduler tracer userspace loader
    add_executable(sched_tracer
        ebpf/sched_tracer.c
    )
    
    # Link with libbpf and dependencies
    target_link_libraries(sched_tracer
        bpf
        elf
        z
    )
    
    # Ensure BPF object is built first
    add_dependencies(sched_tracer sched_tracer_bpf)
    
    # Installation
    install(TARGETS sched_tracer DESTINATION bin)
    install(FILES ${SCHED_BPF_OBJECT} DESTINATION bin)
    
    message(STATUS "✓ eBPF scheduler tracer will be built")
    
    # ========================================================================
    # Page Fault Tracer
    # ========================================================================
    
    set(PAGEFAULT_BPF_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/page_fault_tracer.bpf.c)
    set(PAGEFAULT_BPF_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/page_fault_tracer.bpf.o)
    
    # Prepare dependencies for page fault tracer (vmlinux.h always required)
    set(PAGEFAULT_BPF_DEPENDS ${PAGEFAULT_BPF_SOURCE} ${VMLINUX_H})
    
    # Compile page fault BPF program
    add_custom_command(
        OUTPUT ${PAGEFAULT_BPF_OBJECT}
        COMMAND ${CLANG}
            ${BPF_CFLAGS}
            -I${CMAKE_SOURCE_DIR}/src
            -I${CMAKE_CURRENT_BINARY_DIR}
            -c ${PAGEFAULT_BPF_SOURCE}
            -o ${PAGEFAULT_BPF_OBJECT}
        DEPENDS ${PAGEFAULT_BPF_DEPENDS}
        COMMENT "Compiling BPF program: ${PAGEFAULT_BPF_OBJECT}"
        VERBATIM
    )
    
    # Page fault BPF object build target
    add_custom_target(page_fault_tracer_bpf ALL DEPENDS ${PAGEFAULT_BPF_OBJECT})
    
    # Strip debug info if available
    if(LLVM_STRIP)
        add_custom_command(
            TARGET page_fault_tracer_bpf POST_BUILD
            COMMAND ${LLVM_STRIP} -g ${PAGEFAULT_BPF_OBJECT}
            COMMENT "Stripping BPF debug symbols"
        )
    endif()
    
    # Page fault tracer userspace loader
    add_executable(page_fault_tracer
        ebpf/page_fault_tracer.c
    )
    
    # Link with libbpf and dependencies
    target_link_libraries(page_fault_tracer
        bpf
        elf
        z
    )
    
    # Ensure BPF object is built first
    add_dependencies(page_fault_tracer page_fault_tracer_bpf)
    
    # Installation
    install(TARGETS page_fault_tracer DESTINATION bin)
    install(FILES ${PAGEFAULT_BPF_OBJECT} DESTINATION bin)
    
    message(STATUS "✓ eBPF page fault tracer will be built")
    
    # ========================================================================
    # I/O Latency Tracer
    # ========================================================================
    
    set(IO_BPF_SOURCE ${CMAKE_CURRENT_SOURCE_DIR}/ebpf/io_latency_tracer.bpf.c)
    set(IO_BPF_OBJECT ${CMAKE_CURRENT_BINARY_DIR}/io_latency_tracer.bpf.o)
    
    # Prepare dependencies for I/O latency tracer (vmlinux.h always required)
    set(IO_BPF_DEPENDS ${IO_BPF_SOURCE} ${VMLINUX_H})
    
    # Compile I/O latency BPF program
    add_custom_command(
        OUTPUT ${IO_BPF_OBJECT}
        COMMAND ${CLANG}
            ${BPF_CFLAGS}
            -I${CMAKE_SOURCE_DIR}/src
            -I${CMAKE_CURRENT_BINARY_DIR}
            -c ${IO_BPF_SOURCE}
            -o ${IO_BPF_OBJECT}
        DEPENDS ${IO_BPF_DEPENDS}
        COMMENT "Compiling BPF program: ${IO_BPF_OBJECT}"
        VERBATIM
    )
    
    # I/O latency BPF object build target
    add_custom_target(io_latency_tracer_bpf ALL DEPENDS ${IO_BPF_OBJECT})
    
    # Strip debug info if available
    if(LLVM_STRIP)
        add_custom_command(
            TARGET io_latency_tracer_bpf POST_BUILD
            COMMAND ${LLVM_STRIP} -g ${IO_BPF_OBJECT}
            COMMENT "Stripping BPF debug symbols"
        )
    endif()
    
    # I/O latency tracer userspace loader
    add_executable(io_latency_tracer
        ebpf/io_latency_tracer.c
    )
    
    # Link with libbpf and dependencies (needs math library for percentile calculation)
    target_link_libraries(io_latency_tracer
        bpf
        elf
        z
        m
    )
    
    # Ensure BPF object is built first
    add_dependencies(io_latency_tracer io_latency_tracer_bpf)
    
    # Installation
    install(TARGETS io_latency_tracer DESTINATION bin)
    install(FILES ${IO_BPF_OBJECT} DESTINATION bin)
    
    message(STATUS "✓ eBPF I/O latency tracer will be built")
else()
    message(STATUS "✗ eBPF programs disabled (use -DBUILD_EBPF=ON to enable)")
endif()

# ============================================================================
# Sysfs/Procfs Scraper Daemon (Day 4)
# ============================================================================

# The scraper daemon does not depend on eBPF, so it can always be built
add_executable(scraper_daemon
    sysfs/scraper_daemon.c
    sysfs/proc_scraper.c
    sysfs/sysfs_scraper.c
    sysfs/net_stats.c
)

# No external dependencies needed (uses standard C library)

# Installation
install(TARGETS scraper_daemon DESTINATION bin)

message(STATUS "✓ Sysfs/Procfs scraper daemon will be built")

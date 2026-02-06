#!/bin/bash
# Script to generate syscall_names.h from ausyscall
# This ensures we have the correct syscall mappings for the system

set -e

OUTPUT_FILE="${1:-syscall_names.h}"

# Check if ausyscall is available
if ! command -v ausyscall &> /dev/null; then
    echo "Error: ausyscall not found. Please install auditd package:" >&2
    echo "  Ubuntu: sudo apt-get install auditd" >&2
    echo "  Fedora: sudo dnf install audit" >&2
    exit 1
fi

# Generate header file
cat > "$OUTPUT_FILE" << 'EOF'
// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Auto-generated syscall number to name mapping
// Generated from ausyscall --dump

#ifndef KERNELSIGHT_SYSCALL_NAMES_H
#define KERNELSIGHT_SYSCALL_NAMES_H

#include <stddef.h>

EOF

echo "Generating syscall mapping array..."

# Get syscall list and generate C array
echo "static const char *syscall_names[] = {" >> "$OUTPUT_FILE"

# Parse ausyscall output and create array initializers
ausyscall --dump | awk '
BEGIN { 
    max_nr = 0
}
/^[0-9]/ {
    nr = $1
    name = $2
    
    # Track maximum syscall number
    if (nr > max_nr) max_nr = nr
    
    # Store mapping
    syscalls[nr] = name
}
END {
    # Generate array with all entries up to max
    for (i = 0; i <= max_nr; i++) {
        if (i in syscalls) {
            printf "    [%d] = \"%s\",\n", i, syscalls[i]
        }
    }
}
' >> "$OUTPUT_FILE"

echo "};" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

#define MAX_SYSCALL_NR (sizeof(syscall_names) / sizeof(syscall_names[0]))

static inline const char *get_syscall_name(unsigned int nr)
{
    if (nr < MAX_SYSCALL_NR && syscall_names[nr] != NULL) {
        return syscall_names[nr];
    }
    return "unknown";
}

#endif  // KERNELSIGHT_SYSCALL_NAMES_H
EOF

echo "Successfully generated $OUTPUT_FILE"
echo "Syscall count: $(ausyscall --dump | wc -l)"

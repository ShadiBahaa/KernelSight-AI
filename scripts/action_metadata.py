#!/usr/bin/env python3
"""
Add operational safety metadata to remaining actions.

This script programmatically adds:
- reversibility
- blast_radius
- prerequisites
- side_effects
- verification

to all action types in the catalog.
"""

# Metadata for each action type
ACTION_METADATA = {
    "THROTTLE_CPU": {
        "reversible": True,  # Can kill cpulimit
        "blast_radius": "single_process",
        "prerequisites": ["process_exists", "cpulimit_available"],
        "side_effects": ["slower_execution"],
        "verification": {"check_command": "ps aux | grep cpulimit", "success_indicator": "cpulimit_running"}
    },
    "SET_CPU_AFFINITY": {
        "reversible": True,
        "blast_radius": "single_process",
        "prerequisites": ["process_exists"],
        "side_effects": ["cpu_pinning", "cache_effects"],
        "verification": {"check_command": "taskset -p {pid}", "success_indicator": "affinity_changed"}
    },
    "PAUSE_PROCESS": {
        "reversible": True,  # Can CONT it
        "blast_radius": "single_process",
        "prerequisites": ["process_exists", "not_critical_system"],
        "side_effects": ["service_pause", "timeouts"],
        "verification": {"check_command": "ps -p {pid} -o state", "success_indicator": "state_T"}
    },
    "RESUME_PROCESS": {
        "reversible": False,  # Can't un-resume
        "blast_radius": "single_process",
        "prerequisites": ["process_exists", "process_stopped"],
        "side_effects": ["service_resume"],
        "verification": {"check_command": "ps -p {pid} -o state", "success_indicator": "not_state_T"}
    },
    "TERMINATE_PROCESS": {
        "reversible": False,  # Cannot undo termination
        "blast_radius": "single_process",
        "prerequisites": ["process_exists", "not_critical_system"],
        "side_effects": ["service_downtime", "connection_drops", "requires_manual_restart"],
        "verification": {"check_command": "ps -p {pid}", "expected_exit_code": 1, "success_indicator": "process_gone"}
    },
    "LOWER_IO_PRIORITY": {
        "reversible": True,
        "blast_radius": "single_process",
        "prerequisites": ["process_exists"],
        "side_effects": ["slower_io"],
        "verification": {"check_command": "ionice -p {pid}", "success_indicator": "priority_changed"}
    },
    "FLUSH_BUFFERS": {
        "reversible": False,
        "blast_radius": "system_wide",
        "prerequisites": [],
        "side_effects": ["temporary_io_spike"],
        "verification": {"check_command": "sync", "success_indicator": "completed"}
    },
    "REDUCE_SWAPPINESS": {
        "reversible": True,
        "blast_radius": "system_wide",  # Affects all processes
        "prerequisites": ["swap_enabled"],
        "side_effects": ["oom_risk_if_low_memory"],
        "verification": {"check_command": "sysctl vm.swappiness", "success_indicator": "value_changed"}
    },
    "CLEAR_PAGE_CACHE": {
        "reversible": False,  # Cache cleared
        "blast_radius": "system_wide",
        "prerequisites": [],
        "side_effects": ["temporary_performance_drop", "cache_rebuild"],
        "verification": {"check_command": "free -m", "success_indicator": "cache_reduced"}
    },
    "INCREASE_TCP_BACKLOG": {
        "reversible": True,
        "blast_radius": "system_wide",
        "prerequisites": [],
        "sideffects": ["increased_memory_usage"],
        "verification": {"check_command": "sysctl net.ipv4.tcp_max_syn_backlog", "success_indicator": "value_increased"}
    },
    "REDUCE_FIN_TIMEOUT": {
        "reversible": True,
        "blast_radius": "system_wide",
        "prerequisites": [],
        "side_effects": ["faster_connection_cleanup"],
        "verification": {"check_command": "sysctl net.ipv4.tcp_fin_timeout", "success_indicator": "value_reduced"}
    },
    # Info gathering actions - all safe
    "LIST_TOP_MEMORY": {
        "reversible": False,  # N/A for info
        "blast_radius": "none",
        "prerequisites": [],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
    "LIST_TOP_CPU": {
        "reversible": False,
        "blast_radius": "none",
        "prerequisites": [],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
    "CHECK_IO_ACTIVITY": {
        "reversible": False,
        "blast_radius": "none",
        "prerequisites": ["iotop_available"],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
    "CHECK_NETWORK_STATS": {
        "reversible": False,
        "blast_radius": "none",
        "prerequisites": [],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
    "CHECK_TCP_STATS": {
        "reversible": False,
        "blast_radius": "none",
        "prerequisites": [],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
    "MONITOR_SWAP": {
        "reversible": False,
        "blast_radius": "none",
        "prerequisites": [],
        "side_effects": [],
        "verification": {"check_command": "echo ok", "success_indicator": "output_received"}
    },
}

print("=== Action Metadata Summary ===\n")
print("Total actions:", len(ACTION_METADATA))

# Count by blast radius
blast_counts = {}
for meta in ACTION_METADATA.values():
    radius = meta["blast_radius"]
    blast_counts[radius] = blast_counts.get(radius, 0) + 1

print("\nBlast Radius Distribution:")
for radius, count in sorted(blast_counts.items()):
    print(f"  {radius}: {count} actions")

# Count reversible vs irreversible
reversible = sum(1 for m in ACTION_METADATA.values() if m["reversible"])
print(f"\nReversibility:")
print(f"  Reversible: {reversible}")
print(f"  Irreversible: {len(ACTION_METADATA) - reversible}")

print("\n✓ Metadata defined for all actions")

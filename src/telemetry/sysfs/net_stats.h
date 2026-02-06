// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Network statistics scraper for /proc/net/*

#ifndef NET_STATS_H
#define NET_STATS_H

#include <stdint.h>

// Per-interface statistics from /proc/net/dev
struct interface_stats {
    char name[16]; // Interface name (eth0, wlan0, lo, etc.)
    uint64_t rx_bytes;
    uint64_t rx_packets;
    uint64_t rx_errors;
    uint64_t rx_drops;
    uint64_t tx_bytes;
    uint64_t tx_packets;
    uint64_t tx_errors;
    uint64_t tx_drops;
};

// TCP connection states from /proc/net/tcp
struct tcp_stats {
    uint32_t established;
    uint32_t syn_sent;
    uint32_t syn_recv;
    uint32_t fin_wait1;
    uint32_t fin_wait2;
    uint32_t time_wait;
    uint32_t close;
    uint32_t close_wait;
    uint32_t last_ack;
    uint32_t listen;
    uint32_t closing;
};

// TCP retransmits from /proc/net/snmp
struct tcp_retransmit_stats {
    uint64_t retrans_segs; // Total TCP segments retransmitted
};

/**
 * Read network interface statistics from /proc/net/dev
 * @param interfaces Output array of interface stats (caller must free)
 * @param count Output number of interfaces found
 * @return 0 on success, -1 on error
 */
int read_net_dev(struct interface_stats **interfaces, int *count);

/**
 * Read TCP connection states from /proc/net/tcp and /proc/net/tcp6
 * @param stats Output structure for TCP connection stats
 * @return 0 on success, -1 on error
 */
int read_tcp_stats(struct tcp_stats *stats);

/**
 * Read TCP retransmit statistics from /proc/net/snmp
 * @param stats Output structure for retransmit stats
 * @return 0 on success, -1 on error
 */
int read_tcp_retransmits(struct tcp_retransmit_stats *stats);

/**
 * Print interface stats as JSON to stdout
 * @param iface Interface statistics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_interface_stats_json(const struct interface_stats *iface, uint64_t timestamp);

/**
 * Print TCP connection stats as JSON to stdout
 * @param stats TCP connection statistics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_tcp_stats_json(const struct tcp_stats *stats, uint64_t timestamp);

/**
 * Print TCP retransmit stats as JSON to stdout
 * @param stats TCP retransmit statistics to print
 * @param timestamp Timestamp in nanoseconds
 */
void print_tcp_retransmit_json(const struct tcp_retransmit_stats *stats, uint64_t timestamp);

/**
 * Free memory allocated by read_net_dev
 * @param interfaces Array of interface stats
 * @param count Number of interfaces
 */
void free_interface_stats(struct interface_stats *interfaces, int count);

#endif // NET_STATS_H
